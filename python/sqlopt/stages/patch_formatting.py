from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..io_utils import read_jsonl
from ..run_paths import canonical_paths
from .patching_render import range_offsets as _range_offsets

_MAJOR_SQL_BREAKS = (
    r"UNION\s+ALL",
    r"UNION",
    r"SELECT",
    r"FROM",
    r"WHERE",
    r"GROUP\s+BY",
    r"HAVING",
    r"ORDER\s+BY",
    r"LIMIT",
    r"OFFSET",
    r"SET",
    r"VALUES",
    r"LEFT\s+OUTER\s+JOIN",
    r"RIGHT\s+OUTER\s+JOIN",
    r"FULL\s+OUTER\s+JOIN",
    r"INNER\s+JOIN",
    r"LEFT\s+JOIN",
    r"RIGHT\s+JOIN",
    r"FULL\s+JOIN",
    r"JOIN",
)

_XML_TAG_TOKEN_RE = re.compile(r"(<[^>]+>)")
_DUPLICATE_CLAUSE_TOKEN_RE = re.compile(r"\b(GROUP\s+BY|ORDER\s+BY|FROM|WHERE|LIMIT)\b", flags=re.IGNORECASE)


def _split_sql_by_quotes(sql: str) -> list[tuple[str, bool]]:
    parts: list[tuple[str, bool]] = []
    if not sql:
        return parts
    buf: list[str] = []
    in_single = False
    in_double = False
    idx = 0
    while idx < len(sql):
        ch = sql[idx]
        if in_single:
            buf.append(ch)
            if ch == "'":
                if idx + 1 < len(sql) and sql[idx + 1] == "'":
                    # Escaped single quote inside SQL literal.
                    buf.append("'")
                    idx += 1
                else:
                    parts.append(("".join(buf), True))
                    buf = []
                    in_single = False
            idx += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                parts.append(("".join(buf), True))
                buf = []
                in_double = False
            idx += 1
            continue
        if ch == "'":
            if buf:
                parts.append(("".join(buf), False))
                buf = []
            buf.append(ch)
            in_single = True
            idx += 1
            continue
        if ch == '"':
            if buf:
                parts.append(("".join(buf), False))
                buf = []
            buf.append(ch)
            in_double = True
            idx += 1
            continue
        buf.append(ch)
        idx += 1
    if buf:
        parts.append(("".join(buf), in_single or in_double))
    return parts


def _format_unquoted_sql_segment(segment: str) -> str:
    text = " ".join(str(segment or "").split())
    if not text:
        return ""
    for pattern in _MAJOR_SQL_BREAKS:
        text = re.sub(rf"\s+({pattern})\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(AND|OR)\b", r"\n  \1", text, flags=re.IGNORECASE)
    return text.strip()


def format_sql_for_patch(sql: str) -> str:
    """Render SQL in a patch-friendly multi-line layout without changing semantics."""
    text = str(sql or "").strip()
    if not text:
        return ""
    out_parts: list[str] = []
    for segment, quoted in _split_sql_by_quotes(text):
        if quoted:
            out_parts.append(segment)
        else:
            out_parts.append(_format_unquoted_sql_segment(segment))
    formatted = "".join(out_parts)
    formatted = re.sub(r"[ \t]+\n", "\n", formatted)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    lines = [line.rstrip() for line in formatted.splitlines()]
    return "\n".join(lines).strip()


def _format_template_after_template_for_patch(template_text: str) -> str:
    text = str(template_text or "").strip()
    if not text:
        return ""
    parts = _XML_TAG_TOKEN_RE.split(text)
    merged: list[tuple[str, bool]] = []
    for part in parts:
        if not part:
            continue
        token = part.strip()
        if token.startswith("<") and token.endswith(">"):
            merged.append((token, True))
            continue
        formatted = format_sql_for_patch(token)
        if formatted:
            merged.append((formatted, False))
    if not merged:
        return text

    out = ""
    for token, is_xml_tag in merged:
        if not out:
            out = token
            continue
        if is_xml_tag:
            if out.endswith((" ", "\n")):
                out += token
            else:
                out += " " + token
            continue
        if out.endswith("\n"):
            out += token
        else:
            out += "\n" + token
    return out.strip()


def _load_range_segment(xml_path: Path, range_info: dict[str, Any]) -> tuple[str, bool]:
    if not xml_path.exists() or not isinstance(range_info, dict):
        return "", False
    text = xml_path.read_text(encoding="utf-8")
    offsets = _range_offsets(text, range_info)
    if offsets is None:
        return "", False
    start, end = offsets
    segment = text[start:end]
    return segment, bool(segment and segment[0].isspace())


def _infer_indent_prefix(segment: str) -> str:
    lines = str(segment or "").splitlines()
    candidates: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("</"):
            continue
        prefix = line[: len(line) - len(line.lstrip(" \t"))]
        if prefix:
            candidates.append(prefix)
    if not candidates:
        return "    "
    return min(candidates, key=lambda item: len(item.expandtabs(8)))


def _resolve_template_indent_context(
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    run_dir: Path,
    op: dict[str, Any],
) -> tuple[str, bool]:
    op_name = str(op.get("op") or "").strip()
    if op_name == "replace_statement_body":
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        range_info = ((sql_unit.get("locators") or {}) if isinstance(sql_unit.get("locators"), dict) else {}).get("range")
        segment, has_leading_ws = _load_range_segment(xml_path, range_info if isinstance(range_info, dict) else {})
        return _infer_indent_prefix(segment), has_leading_ws
    if op_name == "replace_fragment_body":
        target_ref = str(op.get("targetRef") or (acceptance.get("rewriteMaterialization") or {}).get("targetRef") or "").strip()
        fragments_path = canonical_paths(run_dir).scan_fragments_path
        if not target_ref or not fragments_path.exists():
            return "    ", False
        fragment_rows = read_jsonl(fragments_path)
        fragment = next((row for row in fragment_rows if str(row.get("fragmentKey") or "") == target_ref), None)
        if fragment is None:
            return "    ", False
        xml_path = Path(str(fragment.get("xmlPath") or ""))
        range_info = ((fragment.get("locators") or {}) if isinstance(fragment.get("locators"), dict) else {}).get("range")
        segment, has_leading_ws = _load_range_segment(xml_path, range_info if isinstance(range_info, dict) else {})
        return _infer_indent_prefix(segment), has_leading_ws
    return "    ", False


def _align_template_indentation(template_text: str, indent: str, has_leading_ws: bool) -> str:
    lines = str(template_text or "").splitlines()
    if len(lines) <= 1:
        return str(template_text or "").strip()
    out: list[str] = []
    for idx, line in enumerate(lines):
        if not line.strip():
            out.append(line)
            continue
        if idx == 0:
            first = line.lstrip(" \t")
            if has_leading_ws:
                out.append(first)
            else:
                out.append(f"{indent}{first}" if indent else first)
            continue
        out.append(f"{indent}{line}" if indent else line)
    return "\n".join(out).strip()


def format_template_ops_for_patch(sql_unit: dict[str, Any], acceptance: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    ops = acceptance.get("templateRewriteOps") or []
    if not isinstance(ops, list) or not ops:
        return acceptance
    changed = False
    formatted_ops: list[dict[str, Any] | Any] = []
    for row in ops:
        if not isinstance(row, dict):
            formatted_ops.append(row)
            continue
        after_template = row.get("afterTemplate")
        if not isinstance(after_template, str) or not after_template.strip():
            formatted_ops.append(row)
            continue
        formatted = _format_template_after_template_for_patch(after_template)
        indent, has_leading_ws = _resolve_template_indent_context(sql_unit, acceptance, run_dir, row)
        aligned = _align_template_indentation(formatted, indent, has_leading_ws)
        if not aligned or aligned == after_template:
            formatted_ops.append(row)
            continue
        next_row = dict(row)
        next_row["afterTemplate"] = aligned
        formatted_ops.append(next_row)
        changed = True
    if not changed:
        return acceptance
    next_acceptance = dict(acceptance)
    next_acceptance["templateRewriteOps"] = formatted_ops
    return next_acceptance


def _find_duplicate_major_clause(template_text: str) -> str | None:
    plain = _XML_TAG_TOKEN_RE.sub(" ", str(template_text or " "))
    plain = " ".join(plain.split())
    matches = [
        (m.start(), m.end(), " ".join(str(m.group(1)).upper().split()))
        for m in _DUPLICATE_CLAUSE_TOKEN_RE.finditer(plain)
    ]
    for left, right in zip(matches, matches[1:]):
        if left[2] != right[2]:
            continue
        between = plain[left[1] : right[0]]
        if between.strip() and "(" not in between and ")" not in between:
            return left[2]
    return None


def detect_duplicate_clause_in_template_ops(acceptance: dict[str, Any]) -> str | None:
    for row in (acceptance.get("templateRewriteOps") or []):
        if not isinstance(row, dict):
            continue
        duplicate_clause = _find_duplicate_major_clause(str(row.get("afterTemplate") or ""))
        if duplicate_clause:
            return duplicate_clause
    return None
