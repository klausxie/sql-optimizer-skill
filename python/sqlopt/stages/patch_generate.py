from __future__ import annotations

import difflib
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl
from ..manifest import log_event
from ..platforms.sql.materialization_constants import TEMPLATE_SAFE_MODES


def _statement_key(sql_key: str) -> str:
    return sql_key.split("#", 1)[0]


def _render_sql_block(sql: str) -> str:
    lines = [line.strip() for line in str(sql).strip().splitlines() if line.strip()]
    if not lines:
        return "\n  "
    return "\n" + "\n".join(f"    {line}" for line in lines) + "\n  "


def _render_template_body(existing_body: str, replacement_body: str) -> str:
    existing = str(existing_body or "")
    replacement = str(replacement_body or "").strip()
    if not replacement:
        return existing
    leading = re.match(r"\s*", existing)
    trailing = re.search(r"\s*$", existing)
    lead = leading.group(0) if leading else ""
    tail = trailing.group(0) if trailing else ""
    return lead + replacement + tail


def _normalize_sql_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _qualify_ref(namespace: str, refid: str | None) -> str:
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


def _collect_sql_fragments(root: ET.Element, namespace: str) -> dict[str, ET.Element]:
    out: dict[str, ET.Element] = {}
    for node in root:
        if _local_name(str(node.tag)).lower() != "sql":
            continue
        ref = _qualify_ref(namespace, node.attrib.get("id"))
        if ref:
            out[ref] = node
    return out


def _render_logical_text(node: ET.Element, namespace: str, fragments: dict[str, ET.Element], stack: set[str] | None = None) -> str:
    stack = set() if stack is None else set(stack)
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        tag = _local_name(str(child.tag)).lower()
        if tag == "include":
            ref = _qualify_ref(namespace, child.attrib.get("refid"))
            target = fragments.get(ref)
            if ref and target is not None and ref not in stack:
                next_stack = set(stack)
                next_stack.add(ref)
                parts.append(_render_logical_text(target, namespace, fragments, next_stack))
        else:
            parts.append(_render_logical_text(child, namespace, fragments, stack))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _split_by_anchors(text: str, anchors: list[str]) -> list[str] | None:
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


def _build_template_with_preserved_includes(
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
    fragments = _collect_sql_fragments(root, namespace)
    statement_node: ET.Element | None = None
    for node in root:
        if _local_name(str(node.tag)).lower() not in {"select", "update", "delete", "insert"}:
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
        if _local_name(str(child.tag)).lower() != "include":
            if _normalize_sql_text(ET.tostring(child, encoding="unicode")):
                return None, None
            continue
        include_tag = ET.tostring(child, encoding="unicode").strip()
        include_ref = _qualify_ref(namespace, child.attrib.get("refid"))
        fragment = fragments.get(include_ref)
        if not include_tag or not include_ref or fragment is None:
            return None, None
        anchor = _normalize_sql_text(_render_logical_text(fragment, namespace, fragments, {include_ref}))
        if not anchor:
            return None, None
        include_tags.append(include_tag)
        include_anchors.append(anchor)
    if not include_tags:
        return None, None

    original_parts = _split_by_anchors(_normalize_sql_text(original_sql), include_anchors)
    if original_parts is None:
        return None, None
    rewritten_parts = _split_by_anchors(_normalize_sql_text(rewritten_sql), include_anchors)
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


def node_has_non_include_dynamic_children(node: ET.Element) -> bool:
    dynamic_tags = {"foreach", "if", "choose", "where", "trim", "set", "bind"}
    for child in list(node):
        name = _local_name(str(child.tag)).lower()
        if name in dynamic_tags:
            return True
        if name not in {"include"}:
            if _normalize_sql_text(ET.tostring(child, encoding="unicode")):
                return True
    return False


def _build_unified_patch(xml_path: Path, statement_id: str, statement_type: str, rewritten_sql: str) -> tuple[str | None, int]:
    original = xml_path.read_text(encoding="utf-8")
    tag = (statement_type or "select").strip().lower()
    # Match one mapper statement by id and replace its inner SQL block.
    pattern = re.compile(
        rf"(<{tag}\b[^>]*\bid=\"{re.escape(statement_id)}\"[^>]*>)([\s\S]*?)(</{tag}>)",
        flags=re.IGNORECASE,
    )
    m = pattern.search(original)
    if not m:
        return None, 0
    replaced = original[: m.start()] + m.group(1) + _render_sql_block(rewritten_sql) + m.group(3) + original[m.end() :]
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


def _offset_from_line_col(text: str, line: int, col: int) -> int:
    if line <= 1:
        return max(0, col - 1)
    current_line = 1
    idx = 0
    while idx < len(text) and current_line < line:
        if text[idx] == "\n":
            current_line += 1
        idx += 1
    return min(len(text), idx + max(0, col - 1))


def _range_offsets(text: str, range_info: dict) -> tuple[int, int] | None:
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
        s = _offset_from_line_col(text, int(start_line), int(start_col))
        e = _offset_from_line_col(text, int(end_line), int(end_col))
        return min(s, e), max(s, e)
    return None


def _build_range_patch(xml_path: Path, range_info: dict, replacement_body: str) -> tuple[str | None, int]:
    original = xml_path.read_text(encoding="utf-8")
    offsets = _range_offsets(original, range_info)
    if offsets is None:
        return None, 0
    start, end = offsets
    replaced = original[:start] + _render_template_body(original[start:end], replacement_body) + original[end:]
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


def _check_patch_applicable(patch_file: Path, workdir: Path) -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(
            ["git", "apply", "--check", str(patch_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, None
    detail = (proc.stderr or proc.stdout or "git apply --check failed").strip()
    return False, detail


def _skip_patch_result(
    *,
    sql_key: str,
    statement_key: str,
    reason_code: str,
    reason_message: str,
    candidates_evaluated: int,
    selected_candidate_id: str | None = None,
    applicable: bool | None = None,
    apply_check_error: str | None = None,
) -> dict:
    patch = {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [],
        "diffSummary": {"skipped": True},
        "applyMode": "PATCH_ONLY",
        "rollback": "not_applied",
        "selectionReason": {"code": reason_code, "message": reason_message},
        "rejectedCandidates": [{"reason_code": reason_code}],
        "candidatesEvaluated": candidates_evaluated,
    }
    if selected_candidate_id is not None:
        patch["selectedCandidateId"] = selected_candidate_id
    if applicable is not None:
        patch["applicable"] = applicable
        patch["applyCheckError"] = apply_check_error
    return patch


def _selected_patch_result(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
) -> dict:
    return {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [str(patch_file)],
        "diffSummary": {"lines": changed_lines, "changed": bool(changed_lines)},
        "applyMode": "PATCH_ONLY",
        "rollback": "delete_patch_file",
        "selectedCandidateId": selected_candidate_id,
        "candidatesEvaluated": candidates_evaluated,
        "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "single pass variant"},
        "rejectedCandidates": [],
        "applicable": True,
        "applyCheckError": None,
    }


def _finalize_generated_patch(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    patch_text: str,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
    no_effect_message: str,
) -> dict:
    patch_file.write_text(patch_text, encoding="utf-8")
    if changed_lines <= 0:
        return _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message=no_effect_message,
            candidates_evaluated=candidates_evaluated,
        )
    applicable, apply_error = _check_patch_applicable(patch_file, Path.cwd().resolve())
    if not applicable:
        return _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NOT_APPLICABLE",
            reason_message="generated patch cannot apply",
            candidates_evaluated=candidates_evaluated,
            selected_candidate_id=selected_candidate_id,
            applicable=False,
            apply_check_error=apply_error,
        )
    return _selected_patch_result(
        sql_key=sql_key,
        statement_key=statement_key,
        patch_file=patch_file,
        changed_lines=changed_lines,
        candidates_evaluated=candidates_evaluated,
        selected_candidate_id=selected_candidate_id,
    )


def _build_template_plan_patch(sql_unit: dict, acceptance: dict, run_dir: Path) -> tuple[str | None, int, dict | None]:
    materialization = acceptance.get("rewriteMaterialization") or {}
    mode = str(materialization.get("mode") or "").strip()
    ops = [row for row in (acceptance.get("templateRewriteOps") or []) if isinstance(row, dict)]
    if mode not in TEMPLATE_SAFE_MODES:
        return None, 0, None
    if materialization.get("replayVerified") is not True:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "template rewrite cannot be applied without replay verification",
        }
    if not ops:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "template materialization did not include rewrite ops",
        }
    if mode == "STATEMENT_TEMPLATE_SAFE":
        op = next((row for row in ops if str(row.get("op") or "") == "replace_statement_body"), None)
        range_info = ((sql_unit.get("locators") or {}) if isinstance(sql_unit.get("locators"), dict) else {}).get("range")
        if op is None or not isinstance(range_info, dict):
            return None, 0, {
                "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
                "message": "statement template rewrite op missing range locator",
            }
        return _build_range_patch(Path(str(sql_unit.get("xmlPath") or "")), range_info, str(op.get("afterTemplate") or "")) + (None,)

    op = next((row for row in ops if str(row.get("op") or "") == "replace_fragment_body"), None)
    if op is None:
        return None, 0, {
            "code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            "message": "fragment template rewrite op missing",
        }
    target_ref = str(op.get("targetRef") or materialization.get("targetRef") or "").strip()
    fragment_rows = read_jsonl(run_dir / "scan.fragments.jsonl")
    fragment = next((row for row in fragment_rows if str(row.get("fragmentKey") or "") == target_ref), None)
    if fragment is None:
        return None, 0, {
            "code": "PATCH_FRAGMENT_LOCATOR_AMBIGUOUS",
            "message": "fragment locator not found",
        }
    range_info = ((fragment.get("locators") or {}) if isinstance(fragment.get("locators"), dict) else {}).get("range")
    if not isinstance(range_info, dict):
        return None, 0, {
            "code": "PATCH_FRAGMENT_LOCATOR_AMBIGUOUS",
            "message": "fragment range locator missing",
        }
    return _build_range_patch(Path(str(fragment.get("xmlPath") or "")), range_info, str(op.get("afterTemplate") or "")) + (None,)


def execute_one(sql_unit: dict, acceptance: dict, run_dir: Path, validator: ContractValidator) -> dict:
    status = acceptance["status"]
    sql_key = sql_unit["sqlKey"]
    statement_key = _statement_key(sql_key)
    acceptance_rows = read_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl")
    same_statement = [row for row in acceptance_rows if _statement_key(str(row.get("sqlKey", ""))) == statement_key]
    pass_rows = [row for row in same_statement if row.get("status") == "PASS"]
    candidates_evaluated = len(same_statement) or 1
    locators = sql_unit.get("locators") or {}
    if not locators.get("statementId"):
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_LOCATOR_AMBIGUOUS",
            reason_message="missing statement locator",
            candidates_evaluated=candidates_evaluated,
        )
    elif status != "PASS":
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="non-pass acceptance",
            candidates_evaluated=candidates_evaluated,
        )
    elif len(pass_rows) != 1 or str(pass_rows[0].get("sqlKey")) != sql_key:
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="multiple pass variants or winner mismatch",
            candidates_evaluated=candidates_evaluated,
        )
    else:
        patch_file = run_dir / "patches" / f"{sql_key.replace('/', '_')}.patch"
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        statement_id = str((locators.get("statementId") or sql_unit.get("statementId") or "")).strip()
        statement_type = str(sql_unit.get("statementType") or "select").strip().lower()
        original_sql = str(sql_unit.get("sql") or "")
        dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
        dynamic_trace = sql_unit.get("dynamicTrace") or {}
        rewritten_sql = str(acceptance.get("rewrittenSql") or "").strip()
        template_patch_text, template_changed_lines, template_error = _build_template_plan_patch(sql_unit, acceptance, run_dir)
        if template_error is not None:
            patch = _skip_patch_result(
                sql_key=sql_key,
                statement_key=statement_key,
                reason_code=str(template_error["code"]),
                reason_message=str(template_error["message"]),
                candidates_evaluated=candidates_evaluated,
            )
        elif template_patch_text is not None:
            patch = _finalize_generated_patch(
                sql_key=sql_key,
                statement_key=statement_key,
                patch_file=patch_file,
                patch_text=template_patch_text,
                changed_lines=template_changed_lines,
                candidates_evaluated=candidates_evaluated,
                selected_candidate_id=acceptance.get("selectedCandidateId"),
                no_effect_message="rewritten template has no diff",
            )
        elif dynamic_features:
            selection_code = "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"
            selection_message = "dynamic mapper statement cannot be replaced by flattened sql"
            if "INCLUDE" in dynamic_features:
                include_fragments = dynamic_trace.get("includeFragments") or []
                has_dynamic_fragment = any(bool((fragment or {}).get("dynamicFeatures")) for fragment in include_fragments)
                selection_code = "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE"
                if has_dynamic_fragment:
                    selection_message = "included sql fragment contains dynamic template tags and requires fragment-aware rewrite"
                else:
                    selection_message = "statement depends on included sql fragment and requires fragment-aware rewrite"
            patch = _skip_patch_result(
                sql_key=sql_key,
                statement_key=statement_key,
                reason_code=selection_code,
                reason_message=selection_message,
                candidates_evaluated=candidates_evaluated,
            )
        elif "#{" in original_sql and "?" in rewritten_sql and "#{" not in rewritten_sql:
            patch = _skip_patch_result(
                sql_key=sql_key,
                statement_key=statement_key,
                reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
                reason_message="placeholder semantics mismatch",
                candidates_evaluated=candidates_evaluated,
            )
        else:
            patch_text, changed_lines = _build_unified_patch(xml_path, statement_id, statement_type, rewritten_sql)
            if patch_text is None:
                patch = _skip_patch_result(
                    sql_key=sql_key,
                    statement_key=statement_key,
                    reason_code="PATCH_LOCATOR_AMBIGUOUS",
                    reason_message="statement not found in mapper",
                    candidates_evaluated=candidates_evaluated,
                )
            else:
                patch = _finalize_generated_patch(
                    sql_key=sql_key,
                    statement_key=statement_key,
                    patch_file=patch_file,
                    patch_text=patch_text,
                    changed_lines=changed_lines,
                    candidates_evaluated=candidates_evaluated,
                    selected_candidate_id=acceptance.get("selectedCandidateId"),
                    no_effect_message="rewritten sql has no diff",
                )
    validator.validate("patch_result", patch)
    append_jsonl(run_dir / "patches" / "patch.results.jsonl", patch)
    log_event(run_dir / "manifest.jsonl", "patch_generate", "done", {"statement_key": sql_key})
    return patch
