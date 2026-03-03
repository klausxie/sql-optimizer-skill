from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

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
    elif reason_code == "PATCH_NOT_APPLICABLE":
        delivery_outcome = {
            "tier": "MANUAL_REVIEW",
            "reasonCodes": [reason_code],
            "summary": "rewrite is plausible, but the generated patch needs manual conflict resolution",
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

    patch = _attach_patch_diagnostics(patch, sql_unit, acceptance)
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
