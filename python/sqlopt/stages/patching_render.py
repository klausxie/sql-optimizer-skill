from __future__ import annotations

import difflib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..utils import statement_key

# 预编译正则表达式
_WHITESPACE_RE = re.compile(r"\s*")



def render_sql_block(sql: str) -> str:
    lines = [line.strip() for line in str(sql).strip().splitlines() if line.strip()]
    if not lines:
        return "\n  "
    return "\n" + "\n".join(f"    {line}" for line in lines) + "\n  "


def render_template_body(existing_body: str, replacement_body: str) -> str:
    existing = str(existing_body or "")
    replacement = str(replacement_body or "").strip()
    if not replacement:
        return existing
    leading = _WHITESPACE_RE.match(existing)
    trailing = _WHITESPACE_RE.search(existing[::-1])  # 反转字符串匹配末尾空白
    lead = leading.group(0) if leading else ""
    # 计算尾部空白（反转后匹配开头）
    tail_len = len(trailing.group(0)) if trailing else 0
    tail = existing[-tail_len:] if tail_len > 0 else ""
    return lead + replacement + tail


def normalize_sql_text(text: str) -> str:
    return " ".join(str(text or "").split())


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def qualify_ref(namespace: str, refid: str | None) -> str:
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


def collect_sql_fragments(root: ET.Element, namespace: str) -> dict[str, ET.Element]:
    out: dict[str, ET.Element] = {}
    for node in root:
        if local_name(str(node.tag)).lower() != "sql":
            continue
        ref = qualify_ref(namespace, node.attrib.get("id"))
        if ref:
            out[ref] = node
    return out


def render_logical_text(
    node: ET.Element,
    namespace: str,
    fragments: dict[str, ET.Element],
    stack: set[str] | None = None,
) -> str:
    def _apply_where_semantics(text: str) -> str:
        normalized = normalize_sql_text(text)
        if not normalized:
            return ""
        normalized = re.sub(r"^(and|or)\b", "", normalized, flags=re.IGNORECASE).strip()
        return f" WHERE {normalized}" if normalized else ""

    def _apply_set_semantics(text: str) -> str:
        normalized = normalize_sql_text(text)
        normalized = re.sub(r",\s*$", "", normalized).strip()
        return f" SET {normalized}" if normalized else ""

    def _apply_choose_semantics(branches: list[str]) -> str:
        normalized = [normalize_sql_text(branch) for branch in branches if normalize_sql_text(branch)]
        if not normalized:
            return ""
        if len(normalized) == 1:
            return normalized[0]
        return "(" + " OR ".join(normalized) + ")"

    stack = set() if stack is None else set(stack)
    tag = local_name(str(node.tag)).lower() if node.tag is not None else ""
    if tag == "choose":
        branches: list[str] = []
        for child in list(node):
            rendered_child = render_logical_text(child, namespace, fragments, stack)
            if normalize_sql_text(rendered_child):
                branches.append(rendered_child)
        return _apply_choose_semantics(branches)
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        child_tag = local_name(str(child.tag)).lower()
        if child_tag == "include":
            ref = qualify_ref(namespace, child.attrib.get("refid"))
            target = fragments.get(ref)
            if ref and target is not None and ref not in stack:
                next_stack = set(stack)
                next_stack.add(ref)
                parts.append(render_logical_text(target, namespace, fragments, next_stack))
        else:
            parts.append(render_logical_text(child, namespace, fragments, stack))
        if child.tail:
            parts.append(child.tail)
    rendered = "".join(parts)
    if tag == "where":
        return _apply_where_semantics(rendered)
    if tag == "set":
        return _apply_set_semantics(rendered)
    return rendered


def split_by_anchors(text: str, anchors: list[str]) -> list[str] | None:
    pos = 0
    parts: list[str] = []
    for anchor in anchors:
        idx = text.find(anchor, pos)
        if idx < 0:
            return None
        parts.append(text[pos:idx].strip())
        pos = idx + len(anchor)
    parts.append(text[pos:].strip())
    return parts


def node_has_non_include_dynamic_children(node: ET.Element) -> bool:
    dynamic_tags = {"foreach", "if", "choose", "where", "trim", "set", "bind"}
    for child in list(node):
        name = local_name(str(child.tag)).lower()
        if name in dynamic_tags:
            return True
        if name not in {"include"}:
            if normalize_sql_text(ET.tostring(child, encoding="unicode")):
                return True
    return False


def build_template_with_preserved_includes(
    sql_unit: dict,
    original_sql: str,
    rewritten_sql: str,
) -> tuple[str | None, str | None]:
    template_sql = str(sql_unit.get("templateSql") or "")
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    statement_id = str(sql_unit.get("statementId") or (sql_unit.get("locators") or {}).get("statementId") or "").strip()
    namespace = str(sql_unit.get("namespace") or "").strip()
    if not template_sql or not xml_path.exists() or not statement_id:
        return None, None
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return None, None
    fragments = collect_sql_fragments(root, namespace)
    statement_node: ET.Element | None = None
    for node in root:
        if local_name(str(node.tag)).lower() not in {"select", "update", "delete", "insert"}:
            continue
        if str(node.attrib.get("id") or "").strip() == statement_id:
            statement_node = node
            break
    if statement_node is None:
        return None, None

    include_tags: list[str] = []
    include_anchors: list[str] = []
    if node_has_non_include_dynamic_children(statement_node):
        return None, None
    for child in list(statement_node):
        if local_name(str(child.tag)).lower() != "include":
            if normalize_sql_text(ET.tostring(child, encoding="unicode")):
                return None, None
            continue
        include_tag = ET.tostring(child, encoding="unicode").strip()
        include_ref = qualify_ref(namespace, child.attrib.get("refid"))
        fragment = fragments.get(include_ref)
        if not include_tag or not include_ref or fragment is None:
            return None, None
        anchor = normalize_sql_text(render_logical_text(fragment, namespace, fragments, {include_ref}))
        if not anchor:
            return None, None
        include_tags.append(include_tag)
        include_anchors.append(anchor)
    if not include_tags:
        return None, None

    original_parts = split_by_anchors(normalize_sql_text(original_sql), include_anchors)
    if original_parts is None:
        return None, None
    rewritten_parts = split_by_anchors(normalize_sql_text(rewritten_sql), include_anchors)
    if rewritten_parts is None:
        return None, "included fragment content changed"

    rebuilt_parts: list[str] = []
    for idx, include_tag in enumerate(include_tags):
        if rewritten_parts[idx]:
            rebuilt_parts.append(rewritten_parts[idx])
        rebuilt_parts.append(include_tag)
    if rewritten_parts[-1]:
        rebuilt_parts.append(rewritten_parts[-1])
    rebuilt = " ".join(part for part in rebuilt_parts if part).strip()
    return rebuilt or None, None


def build_unified_patch(xml_path: Path, statement_id: str, statement_type: str, rewritten_sql: str) -> tuple[str | None, int]:
    original = xml_path.read_text(encoding="utf-8")
    tag = (statement_type or "select").strip().lower()
    pattern = re.compile(
        rf"(<{tag}\b[^>]*\bid=\"{re.escape(statement_id)}\"[^>]*>)([\s\S]*?)(</{tag}>)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(original)
    if not match:
        return None, 0
    replaced = original[: match.start()] + match.group(1) + render_sql_block(rewritten_sql) + match.group(3) + original[match.end() :]
    if replaced == original:
        return "", 0

    try:
        rel = xml_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        rel = xml_path.as_posix()
    old_lines = original.splitlines()
    new_lines = replaced.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )
    patch_text = "".join(line + "\n" for line in diff_lines)
    changed = sum(1 for line in diff_lines if line.startswith("+") or line.startswith("-"))
    return patch_text, changed


def offset_from_line_col(text: str, line: int, col: int) -> int:
    if line <= 1:
        return max(0, col - 1)
    current_line = 1
    idx = 0
    while idx < len(text) and current_line < line:
        if text[idx] == "\n":
            current_line += 1
        idx += 1
    return min(len(text), idx + max(0, col - 1))


def range_offsets(text: str, range_info: dict) -> tuple[int, int] | None:
    if not isinstance(range_info, dict):
        return None
    start = range_info.get("startOffset")
    end = range_info.get("endOffset")
    if isinstance(start, int) and isinstance(end, int):
        return max(0, start), min(len(text), end)
    start_line = range_info.get("startLine")
    start_col = range_info.get("startColumn")
    end_line = range_info.get("endLine")
    end_col = range_info.get("endColumn")
    if all(isinstance(x, int) for x in (start_line, start_col, end_line, end_col)):
        s = offset_from_line_col(text, int(start_line), int(start_col))
        e = offset_from_line_col(text, int(end_line), int(end_col))
        return min(s, e), max(s, e)
    return None


def build_range_patch(xml_path: Path, range_info: dict, replacement_body: str) -> tuple[str | None, int]:
    original = xml_path.read_text(encoding="utf-8")
    offsets = range_offsets(original, range_info)
    if offsets is None:
        return None, 0
    start, end = offsets
    replaced = original[:start] + render_template_body(original[start:end], replacement_body) + original[end:]
    if replaced == original:
        return "", 0
    try:
        rel = xml_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        rel = xml_path.as_posix()
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            replaced.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )
    patch_text = "".join(line + "\n" for line in diff_lines)
    changed = sum(1 for line in diff_lines if line.startswith("+") or line.startswith("-"))
    return patch_text, changed
