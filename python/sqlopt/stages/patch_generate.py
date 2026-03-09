from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl
from ..manifest import log_event
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record
from .patching_render import (
    build_range_patch as _build_range_patch,
    build_template_with_preserved_includes as _build_template_with_preserved_includes,
    build_unified_patch as _build_unified_patch,
    collect_sql_fragments as _collect_sql_fragments,
    local_name as _local_name,
    node_has_non_include_dynamic_children,
    normalize_sql_text as _normalize_sql_text,
    offset_from_line_col as _offset_from_line_col,
    qualify_ref as _qualify_ref,
    range_offsets as _range_offsets,
    render_logical_text as _render_logical_text,
    render_sql_block as _render_sql_block,
    render_template_body as _render_template_body,
    split_by_anchors as _split_by_anchors,
    statement_key as _statement_key,
)
from .patching_results import selected_patch_result as _selected_patch_result
from .patching_results import skip_patch_result as _skip_patch_result
from .patching_templates import build_template_plan_patch as _build_template_plan_patch
from .patch_generate_llm import (
    generate_template_patch_suggestion as _generate_template_patch_suggestion,
    attach_llm_suggestion_to_patch as _attach_llm_suggestion,
    save_template_suggestion as _save_template_suggestion,
)


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


def _format_sql_for_patch(sql: str) -> str:
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
        formatted = _format_sql_for_patch(token)
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


def _load_range_segment(xml_path: Path, range_info: dict) -> tuple[str, bool]:
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


def _resolve_template_indent_context(sql_unit: dict, acceptance: dict, run_dir: Path, op: dict) -> tuple[str, bool]:
    op_name = str(op.get("op") or "").strip()
    if op_name == "replace_statement_body":
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        range_info = ((sql_unit.get("locators") or {}) if isinstance(sql_unit.get("locators"), dict) else {}).get("range")
        segment, has_leading_ws = _load_range_segment(xml_path, range_info if isinstance(range_info, dict) else {})
        return _infer_indent_prefix(segment), has_leading_ws
    if op_name == "replace_fragment_body":
        target_ref = str(op.get("targetRef") or (acceptance.get("rewriteMaterialization") or {}).get("targetRef") or "").strip()
        fragments_path = run_dir / "scan.fragments.jsonl"
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


def _format_template_ops_for_patch(sql_unit: dict, acceptance: dict, run_dir: Path) -> dict:
    ops = acceptance.get("templateRewriteOps") or []
    if not isinstance(ops, list) or not ops:
        return acceptance
    changed = False
    formatted_ops: list[dict | Any] = []
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


def _detect_duplicate_clause_in_template_ops(acceptance: dict) -> str | None:
    for row in (acceptance.get("templateRewriteOps") or []):
        if not isinstance(row, dict):
            continue
        duplicate_clause = _find_duplicate_major_clause(str(row.get("afterTemplate") or ""))
        if duplicate_clause:
            return duplicate_clause
    return None


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


def _build_patch_repair_hints(reason_code: str, apply_check_error: str | None, sql_unit: dict) -> list[dict]:
    xml_path = str(sql_unit.get("xmlPath") or "").strip()
    if reason_code == "PATCH_NOT_APPLICABLE":
        return [
            {
                "hintId": "review-target-drift",
                "title": "Check target mapper drift",
                "detail": "the generated patch no longer applies cleanly to the current mapper file",
                "actionType": "GIT_CONFLICT",
                "command": f"git diff -- {xml_path}" if xml_path else None,
            }
        ]
    if reason_code == "PATCH_LOCATOR_AMBIGUOUS":
        return [
            {
                "hintId": "stabilize-locator",
                "title": "Stabilize statement locator",
                "detail": "add a stable statementId or preserve enough structure for deterministic targeting",
                "actionType": "MAPPER_REFACTOR",
                "command": None,
            }
        ]
    if reason_code == "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE":
        return [
            {
                "hintId": "expand-include",
                "title": "Refactor include fragment path",
                "detail": "expand or isolate included fragments before relying on automatic patch generation",
                "actionType": "MAPPER_REFACTOR",
                "command": None,
            }
        ]
    if reason_code == "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE":
        return [
            {
                "hintId": "use-template-rewrite",
                "title": "Prefer template-aware rewrite",
                "detail": "this dynamic mapper shape requires template-aware rewriting instead of flattened SQL replacement",
                "actionType": "SQL_REWRITE",
                "command": None,
            }
        ]
    if reason_code == "PATCH_CONFLICT_NO_CLEAR_WINNER":
        return [
            {
                "hintId": "collapse-candidates",
                "title": "Resolve competing winners",
                "detail": "reduce multiple PASS variants before generating a patch",
                "actionType": "MANUAL_PATCH",
                "command": None,
            }
        ]
    if reason_code == "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED":
        return [
            {
                "hintId": "review-template-duplicate-clause",
                "title": "Review duplicate template clause",
                "detail": "template rewrite contains duplicated major SQL clause and needs manual review",
                "actionType": "MANUAL_PATCH",
                "command": None,
            }
        ]
    if apply_check_error:
        return [
            {
                "hintId": "review-apply-error",
                "title": "Inspect apply-check failure",
                "detail": apply_check_error,
                "actionType": "GIT_CONFLICT",
                "command": f"git diff -- {xml_path}" if xml_path else None,
            }
        ]
    return []


def _attach_patch_diagnostics(patch: dict, sql_unit: dict, acceptance: dict) -> dict:
    selection_reason = dict(patch.get("selectionReason") or {})
    reason_code = str(selection_reason.get("code") or "").strip()
    apply_check_error = patch.get("applyCheckError")
    template_ops = [row for row in (acceptance.get("templateRewriteOps") or []) if isinstance(row, dict)]
    replay_verified = (acceptance.get("rewriteMaterialization") or {}).get("replayVerified")
    locator_stable = bool(((sql_unit.get("locators") or {}).get("statementId")))
    template_safe_path = bool(template_ops) and replay_verified is True
    structural_blockers = [reason_code] if reason_code and patch.get("applicable") is not True else []

    if patch.get("applicable") is True:
        delivery_outcome = {
            "tier": "READY_TO_APPLY",
            "reasonCodes": [reason_code or "PATCH_SELECTED_SINGLE_PASS"],
            "summary": "patch is ready to apply",
        }
    elif reason_code in {
        "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE",
        "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
    }:
        delivery_outcome = {
            "tier": "PATCHABLE_WITH_REWRITE",
            "reasonCodes": [reason_code],
            "summary": "patch can likely land after template-aware mapper refactoring",
        }
    elif reason_code in {"PATCH_NOT_APPLICABLE", "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED"}:
        delivery_outcome = {
            "tier": "MANUAL_REVIEW",
            "reasonCodes": [reason_code],
            "summary": (
                "rewrite is plausible, but the generated patch needs manual conflict resolution"
                if reason_code == "PATCH_NOT_APPLICABLE"
                else "template rewrite needs manual review before patch generation"
            ),
        }
    else:
        delivery_outcome = {
            "tier": "BLOCKED",
            "reasonCodes": [reason_code] if reason_code else [],
            "summary": "automatic patch generation is blocked by current mapper or candidate shape",
        }

    patch["deliveryOutcome"] = delivery_outcome
    patch["repairHints"] = _build_patch_repair_hints(reason_code, apply_check_error, sql_unit)
    patch["patchability"] = {
        "applyCheckPassed": True if patch.get("applicable") is True else (False if patch.get("applicable") is False else None),
        "templateSafePath": template_safe_path,
        "locatorStable": locator_stable,
        "structuralBlockers": structural_blockers,
    }
    return patch


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
    workdir: Path,
) -> dict:
    if changed_lines <= 0:
        # No effective change: do not create an empty patch artifact.
        patch_file.unlink(missing_ok=True)
        return _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message=no_effect_message,
            candidates_evaluated=candidates_evaluated,
        )
    patch_file.write_text(patch_text, encoding="utf-8")
    applicable, apply_error = _check_patch_applicable(patch_file, workdir)
    if not applicable:
        return _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NOT_APPLICABLE",
            reason_message="generated patch failed git apply --check against project root",
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


def execute_one(sql_unit: dict, acceptance: dict, run_dir: Path, validator: ContractValidator, config: dict[str, Any] | None = None) -> dict:
    status = acceptance["status"]
    sql_key = sql_unit["sqlKey"]
    statement_key = _statement_key(sql_key)
    acceptance_rows = read_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl")
    same_statement = [row for row in acceptance_rows if _statement_key(str(row.get("sqlKey", ""))) == statement_key]
    pass_rows = [row for row in same_statement if row.get("status") == "PASS"]
    candidates_evaluated = len(same_statement) or 1
    locators = sql_unit.get("locators") or {}

    project_root = Path.cwd().resolve()
    configured_root = str((((config or {}).get("project", {}) or {}).get("root_path") or "")).strip()
    if configured_root:
        candidate_root = Path(configured_root).resolve()
        if candidate_root.exists():
            project_root = candidate_root

    if not locators.get("statementId"):
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_LOCATOR_AMBIGUOUS",
            reason_message="missing locators.statementId in scan output",
            candidates_evaluated=candidates_evaluated,
        )
    elif status != "PASS":
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="acceptance status is not PASS",
            candidates_evaluated=candidates_evaluated,
        )
    elif len(pass_rows) != 1 or str(pass_rows[0].get("sqlKey")) != sql_key:
        patch = _skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="multiple PASS variants found or selected winner mismatched",
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
        formatted_rewritten_sql = _format_sql_for_patch(rewritten_sql)
        if (not dynamic_features) and _normalize_sql_text(original_sql) == _normalize_sql_text(rewritten_sql):
            patch = _skip_patch_result(
                sql_key=sql_key,
                statement_key=statement_key,
                reason_code="PATCH_NO_EFFECTIVE_CHANGE",
                reason_message="rewritten sql has no semantic diff after normalization",
                candidates_evaluated=candidates_evaluated,
            )
        else:
            template_acceptance = _format_template_ops_for_patch(sql_unit, acceptance, run_dir)
            duplicate_clause = _detect_duplicate_clause_in_template_ops(template_acceptance)
            if duplicate_clause:
                patch = _skip_patch_result(
                    sql_key=sql_key,
                    statement_key=statement_key,
                    reason_code="PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED",
                    reason_message=f"template rewrite contains duplicated {duplicate_clause} clause",
                    candidates_evaluated=candidates_evaluated,
                )
                template_patch_text, template_changed_lines, template_error = None, 0, None
            else:
                template_patch_text, template_changed_lines, template_error = _build_template_plan_patch(
                    sql_unit, template_acceptance, run_dir
                )

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
                    workdir=project_root,
                )
            elif duplicate_clause:
                pass
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
                patch_sql = formatted_rewritten_sql or rewritten_sql
                patch_text, changed_lines = _build_unified_patch(xml_path, statement_id, statement_type, patch_sql)
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
                        workdir=project_root,
                    )

    patch = _attach_patch_diagnostics(patch, sql_unit, acceptance)

    # Phase 5: LLM 模板辅助（可选）
    patch_cfg = (config or {}).get("patch", {}) or {}
    llm_assist_cfg = patch_cfg.get("llm_assist", {})
    llm_assist_enabled = bool(llm_assist_cfg.get("enabled", False))
    only_for_dynamic_sql = bool(llm_assist_cfg.get("only_for_dynamic_sql", True))

    llm_suggestion = None
    if llm_assist_enabled:
        # 判断是否需要 LLM 辅助
        dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
        is_dynamic_sql = bool(dynamic_features)

        # 仅在动态 SQL 或配置允许时调用
        if not only_for_dynamic_sql or is_dynamic_sql:
            # 当 patch 被跳过或需要人工审查时，调用 LLM 辅助
            selection_reason = patch.get("selectionReason") or {}
            reason_code = str(selection_reason.get("code") or "")
            should_call_llm = (
                patch.get("applicable") is not True or
                reason_code in {
                    "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
                    "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE",
                    "PATCH_NOT_APPLICABLE",
                }
            )

            if should_call_llm:
                llm_cfg = (config or {}).get("llm", {}) or {}
                llm_suggestion = _generate_template_patch_suggestion(
                    sql_unit=sql_unit,
                    acceptance=acceptance,
                    patch_result=patch,
                    llm_cfg=llm_cfg,
                )

                if llm_suggestion:
                    # 保存建议到文件
                    _save_template_suggestion(run_dir, sql_key, llm_suggestion)
                    # 附加到 patch 结果
                    patch = _attach_llm_suggestion(patch, llm_suggestion)

    validator.validate("patch_result", patch)
    append_jsonl(run_dir / "patches" / "patch.results.jsonl", patch)
    selection_reason = dict(patch.get("selectionReason") or {})
    template_ops = [row for row in (acceptance.get("templateRewriteOps") or []) if isinstance(row, dict)]
    replay_verified = (acceptance.get("rewriteMaterialization") or {}).get("replayVerified")
    applicable = patch.get("applicable")
    selection_code = str(selection_reason.get("code") or "").strip()
    pass_has_clear_winner = status != "PASS" or (len(pass_rows) == 1 and str(pass_rows[0].get("sqlKey") or "") == sql_key)
    checks = [
        VerificationCheck(
            "acceptance_pass_required",
            status == "PASS",
            "warn",
            None if status == "PASS" else "PATCH_ACCEPTANCE_NOT_PASS",
        ),
        VerificationCheck(
            "clear_winner_present",
            pass_has_clear_winner,
            "warn" if status == "PASS" else "info",
            None if pass_has_clear_winner else "PATCH_CONFLICT_NO_CLEAR_WINNER",
        ),
        VerificationCheck(
            "template_replay_verified",
            (not template_ops) or replay_verified is True,
            "error" if template_ops else "info",
            None if (not template_ops) or replay_verified is True else "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED",
        ),
        VerificationCheck(
            "patch_applicability_recorded",
            (applicable is True) or (applicable is False) or bool(selection_code),
            "warn",
            None if (applicable is True) or (applicable is False) or bool(selection_code) else "PATCH_APPLICABILITY_UNKNOWN",
        ),
    ]
    if template_ops and replay_verified is not True:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED"
        verification_reason_message = "template patch path was considered without replay verification"
    elif applicable is True:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_APPLICABLE_VERIFIED"
        verification_reason_message = "patch was selected and passed git apply --check"
    elif applicable is False:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_NOT_APPLICABLE"
        verification_reason_message = "patch was rejected with an explicit apply-check failure"
    elif selection_code:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code
        verification_reason_message = str(selection_reason.get("message") or "patch was skipped for an explicit rule")
    else:
        verification_status = "PARTIAL"
        verification_reason_code = "PATCH_DECISION_EVIDENCE_INCOMPLETE"
        verification_reason_message = "patch result exists but its selection evidence is incomplete"
    append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=statement_key,
            phase="patch_generate",
            status=verification_status,
            reason_code=verification_reason_code,
            reason_message=verification_reason_message,
            evidence_refs=[
                str(run_dir / "acceptance" / "acceptance.results.jsonl"),
                str(run_dir / "patches" / "patch.results.jsonl"),
                *[str(x) for x in (patch.get("patchFiles") or [])],
            ],
            inputs={
                "acceptance_status": status,
                "same_statement_count": len(same_statement),
                "pass_variant_count": len(pass_rows),
                "template_op_count": len(template_ops),
                "replay_verified": replay_verified,
            },
            checks=checks,
            verdict={
                "selection_code": selection_code or None,
                "applicable": applicable,
                "patch_file_count": len(patch.get("patchFiles") or []),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    log_event(run_dir / "manifest.jsonl", "patch_generate", "done", {"statement_key": sql_key})
    return patch
