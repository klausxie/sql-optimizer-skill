from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..run_paths import canonical_paths

@dataclass(frozen=True)
class PatchDecisionContext:
    status: str
    semantic_gate_status: str
    semantic_gate_confidence: str
    sql_key: str
    statement_key: str
    same_statement: list[dict[str, Any]]
    pass_rows: list[dict[str, Any]]
    candidates_evaluated: int


def _acceptance_reason_code(acceptance: dict[str, Any]) -> str | None:
    feedback = acceptance.get("feedback")
    if not isinstance(feedback, dict):
        return None
    code = str(feedback.get("reason_code") or "").strip().upper()
    return code or None


def _fallback_reason_codes(acceptance: dict[str, Any]) -> list[str]:
    out: list[str] = []
    feedback_code = _acceptance_reason_code(acceptance)
    if feedback_code:
        out.append(feedback_code)
    perf = acceptance.get("perfComparison")
    perf_payload = perf if isinstance(perf, dict) else {}
    for code in perf_payload.get("reasonCodes") or []:
        normalized = str(code or "").strip().upper()
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _selection_evidence(
    *,
    status: str,
    semantic_gate_status: str,
    semantic_gate_confidence: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    repairability = dict(acceptance.get("repairability") or {})
    return {
        "acceptanceStatus": status,
        "acceptanceReasonCode": _acceptance_reason_code(acceptance),
        "semanticGateStatus": semantic_gate_status,
        "semanticGateConfidence": semantic_gate_confidence,
        "repairabilityStatus": str(repairability.get("status") or "").strip().upper() or None,
        "rewriteSafetyLevel": str(acceptance.get("rewriteSafetyLevel") or "").strip().upper() or None,
    }


def _dynamic_template_summary(acceptance: dict[str, Any]) -> dict[str, Any]:
    summary = acceptance.get("dynamicTemplate")
    if isinstance(summary, dict):
        return dict(summary)
    rewrite_facts = dict(acceptance.get("rewriteFacts") or {})
    dynamic_template = dict(rewrite_facts.get("dynamicTemplate") or {})
    profile = dict(dynamic_template.get("capabilityProfile") or {})
    patchability = dict(acceptance.get("patchability") or {})
    if not dynamic_template:
        return {}
    return {
        "present": bool(dynamic_template.get("present")),
        "shapeFamily": str(profile.get("shapeFamily") or "").strip() or None,
        "capabilityTier": str(profile.get("capabilityTier") or "").strip() or None,
        "patchSurface": str(profile.get("patchSurface") or "").strip() or None,
        "blockingReason": (
            str(patchability.get("dynamicBlockingReason") or "").strip()
            or str(profile.get("blockerFamily") or "").strip()
            or None
        ),
    }


def _semantic_gate_status(acceptance: dict[str, Any]) -> str:
    gate = acceptance.get("semanticEquivalence")
    if not isinstance(gate, dict):
        # Backward-compatibility for historical acceptance artifacts.
        return "PASS"
    status = str(gate.get("status") or "").strip().upper()
    if status in {"PASS", "FAIL", "UNCERTAIN"}:
        return status
    return "UNCERTAIN"


def _semantic_gate_confidence(acceptance: dict[str, Any]) -> str:
    gate = acceptance.get("semanticEquivalence")
    if not isinstance(gate, dict):
        # Backward-compatibility for historical acceptance artifacts.
        return "HIGH"
    confidence = str(gate.get("confidence") or "").strip().upper()
    if confidence in {"LOW", "MEDIUM", "HIGH"}:
        return confidence
    return "LOW"


def decide_patch_result(
    *,
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    run_dir: Path,
    acceptance_rows: list[dict[str, Any]],
    project_root: Path,
    statement_key_fn: Callable[[str], str],
    skip_patch_result: Callable[..., dict[str, Any]],
    finalize_generated_patch: Callable[..., dict[str, Any]],
    format_sql_for_patch: Callable[[str], str],
    normalize_sql_text: Callable[[str], str],
    format_template_ops_for_patch: Callable[[dict[str, Any], dict[str, Any], Path], dict[str, Any]],
    detect_duplicate_clause_in_template_ops: Callable[[dict[str, Any]], str | None],
    build_template_plan_patch: Callable[[dict[str, Any], dict[str, Any], Path], tuple[str | None, int, dict[str, Any] | None]],
    build_unified_patch: Callable[[Path, str, str, str], tuple[str | None, int]],
) -> tuple[dict[str, Any], PatchDecisionContext]:
    status = acceptance["status"]
    semantic_gate_status = _semantic_gate_status(acceptance)
    semantic_gate_confidence = _semantic_gate_confidence(acceptance)
    sql_key = sql_unit["sqlKey"]
    statement_key = statement_key_fn(sql_key)
    same_statement = [row for row in acceptance_rows if statement_key_fn(str(row.get("sqlKey", ""))) == statement_key]
    pass_rows = [row for row in same_statement if row.get("status") == "PASS"]
    candidates_evaluated = len(same_statement) or 1
    locators = sql_unit.get("locators") or {}
    acceptance_reason_code = _acceptance_reason_code(acceptance)
    fallback_reason_codes = _fallback_reason_codes(acceptance)
    selection_evidence = _selection_evidence(
        status=status,
        semantic_gate_status=semantic_gate_status,
        semantic_gate_confidence=semantic_gate_confidence,
        acceptance=acceptance,
    )

    ctx = PatchDecisionContext(
        status=status,
        semantic_gate_status=semantic_gate_status,
        semantic_gate_confidence=semantic_gate_confidence,
        sql_key=sql_key,
        statement_key=statement_key,
        same_statement=same_statement,
        pass_rows=pass_rows,
        candidates_evaluated=candidates_evaluated,
    )

    if not locators.get("statementId"):
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_LOCATOR_AMBIGUOUS",
            reason_message="missing locators.statementId in scan output",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    if status != "PASS":
        if acceptance_reason_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
            reason_code = "PATCH_VALIDATION_BLOCKED_SECURITY"
            reason_message = "validate blocked patch generation due unsafe ${} substitution"
        else:
            reason_code = "PATCH_CONFLICT_NO_CLEAR_WINNER"
            reason_message = "acceptance status is not PASS"
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code=reason_code,
            reason_message=reason_message,
            candidates_evaluated=candidates_evaluated,
            selected_candidate_id=acceptance.get("selectedCandidateId"),
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    if semantic_gate_status != "PASS":
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
            reason_message=f"semantic equivalence gate is {semantic_gate_status}, patch generation is blocked",
            candidates_evaluated=candidates_evaluated,
            selected_candidate_id=acceptance.get("selectedCandidateId"),
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx
    if semantic_gate_confidence == "LOW":
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_SEMANTIC_CONFIDENCE_LOW",
            reason_message="semantic equivalence confidence is LOW, patch generation is blocked",
            candidates_evaluated=candidates_evaluated,
            selected_candidate_id=acceptance.get("selectedCandidateId"),
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    if len(pass_rows) != 1 or str(pass_rows[0].get("sqlKey")) != sql_key:
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="multiple PASS variants found or selected winner mismatched",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    patch_file = canonical_paths(run_dir).patch_files_dir / f"{sql_key.replace('/', '_')}.patch"
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    statement_id = str((locators.get("statementId") or sql_unit.get("statementId") or "")).strip()
    statement_type = str(sql_unit.get("statementType") or "select").strip().lower()
    original_sql = str(sql_unit.get("sql") or "")
    dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
    dynamic_trace = sql_unit.get("dynamicTrace") or {}
    dynamic_template = _dynamic_template_summary(acceptance)
    rewritten_sql = str(acceptance.get("rewrittenSql") or "").strip()
    formatted_rewritten_sql = format_sql_for_patch(rewritten_sql)

    if (not dynamic_features) and normalize_sql_text(original_sql) == normalize_sql_text(rewritten_sql):
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message="rewritten sql has no semantic diff after normalization",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    template_acceptance = format_template_ops_for_patch(sql_unit, acceptance, run_dir)
    duplicate_clause = detect_duplicate_clause_in_template_ops(template_acceptance)
    if duplicate_clause:
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED",
            reason_message=f"template rewrite contains duplicated {duplicate_clause} clause",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        template_patch_text, template_changed_lines, template_error = None, 0, None
    else:
        template_patch_text, template_changed_lines, template_error = build_template_plan_patch(
            sql_unit, template_acceptance, run_dir
        )

    if template_error is not None:
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code=str(template_error["code"]),
            reason_message=str(template_error["message"]),
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    if template_patch_text is not None:
        patch = finalize_generated_patch(
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
        return patch, ctx

    if duplicate_clause:
        return patch, ctx

    if dynamic_features:
        selection_code = "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"
        selection_message = "dynamic mapper statement cannot be replaced by flattened sql"
        dynamic_blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        dynamic_shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()
        if dynamic_blocking_reason.startswith("FOREACH_") or dynamic_shape_family == "FOREACH_IN_PREDICATE":
            selection_code = "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED"
            selection_message = "dynamic foreach predicate requires template-aware rewrite before patch generation"
        elif dynamic_blocking_reason == "DYNAMIC_FILTER_SUBTREE" or dynamic_shape_family == "IF_GUARDED_FILTER_STATEMENT":
            selection_code = "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED"
            selection_message = "dynamic filter subtree requires template-aware rewrite before patch generation"
        elif dynamic_blocking_reason == "DYNAMIC_SET_CLAUSE" or dynamic_shape_family == "SET_SELECTIVE_UPDATE":
            selection_code = "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED"
            selection_message = "dynamic set clause requires template-aware rewrite before patch generation"
        if "INCLUDE" in dynamic_features:
            include_fragments = dynamic_trace.get("includeFragments") or []
            has_dynamic_fragment = any(bool((fragment or {}).get("dynamicFeatures")) for fragment in include_fragments)
            if selection_code == "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE":
                selection_code = "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE"
            if has_dynamic_fragment or dynamic_blocking_reason == "INCLUDE_DYNAMIC_SUBTREE":
                selection_message = "included sql fragment contains dynamic template tags and requires fragment-aware rewrite"
            elif selection_code == "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE":
                selection_message = "statement depends on included sql fragment and requires fragment-aware rewrite"
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code=selection_code,
            reason_message=selection_message,
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    if "#{" in original_sql and "?" in rewritten_sql and "#{" not in rewritten_sql:
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="placeholder semantics mismatch",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    patch_sql = formatted_rewritten_sql or rewritten_sql
    patch_text, changed_lines = build_unified_patch(xml_path, statement_id, statement_type, patch_sql)
    if patch_text is None:
        patch = skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_LOCATOR_AMBIGUOUS",
            reason_message="statement not found in mapper",
            candidates_evaluated=candidates_evaluated,
            selection_evidence=selection_evidence,
            fallback_reason_codes=fallback_reason_codes,
        )
        return patch, ctx

    patch = finalize_generated_patch(
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
    return patch, ctx
