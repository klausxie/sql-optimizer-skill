from __future__ import annotations

from typing import Any

from .models import AcceptanceDecision, EquivalenceCheck, PerfComparison, ValidationResult


def _terminal_decision_layers(
    *,
    phase: str,
    status: str,
    validation_profile: str,
    feedback_reason_code: str | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "feasibility": {
            "phase": phase,
            "candidate_available": False,
            "db_reachable": phase != "db_unreachable",
            "ready": phase not in {"security_block", "invalid_candidate", "db_unreachable"},
        },
        "evidence": {
            "semantic_checked": phase == "security_block",
            "perf_checked": False,
            "degraded": phase == "db_unreachable",
            "reasonCodes": list(reason_codes or []),
        },
        "acceptance": {
            "status": status,
            "validationProfile": validation_profile,
            "feedbackReasonCode": feedback_reason_code,
        },
    }


def security_failure_result(
    sql_key: str,
    validation_profile: str,
    risk_flags: list[str],
) -> ValidationResult:
    status = "FAIL" if validation_profile == "strict" else "NEED_MORE_PARAMS"
    return ValidationResult(
        sql_key=sql_key,
        status=status,
        equivalence={"checked": True, "method": "static", "evidenceRefs": []},
        perf_comparison={"checked": False, "reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"], "improved": None},
        security_checks={"dollar_substitution_removed": False},
        semantic_risk="high",
        feedback={"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", "message": "unsafe ${} pattern"},
        selected_candidate_source="rule",
        warnings=["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"] if status != "FAIL" else [],
        risk_flags=risk_flags,
        decision_layers=_terminal_decision_layers(
            phase="security_block",
            status=status,
            validation_profile=validation_profile,
            feedback_reason_code="VALIDATE_SECURITY_DOLLAR_SUBSTITUTION",
            reason_codes=["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"],
        ),
    )


def invalid_candidate_result(
    sql_key: str,
    risk_flags: list[str],
    *,
    validation_profile: str = "balanced",
) -> ValidationResult:
    return ValidationResult(
        sql_key=sql_key,
        status="FAIL",
        equivalence={"checked": True, "method": "candidate_sanity", "evidenceRefs": []},
        perf_comparison={"checked": False, "reasonCodes": ["VALIDATE_EQUIVALENCE_MISMATCH"], "improved": None},
        security_checks={"dollar_substitution_removed": False},
        semantic_risk="high",
        feedback={"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH", "message": "invalid candidate sql"},
        selected_candidate_source="llm",
        warnings=[],
        risk_flags=risk_flags,
        decision_layers=_terminal_decision_layers(
            phase="invalid_candidate",
            status="FAIL",
            validation_profile=validation_profile,
            feedback_reason_code="VALIDATE_EQUIVALENCE_MISMATCH",
            reason_codes=["VALIDATE_EQUIVALENCE_MISMATCH"],
        ),
    )


def db_unreachable_result(
    sql_key: str,
    risk_flags: list[str],
    *,
    validation_profile: str = "balanced",
) -> ValidationResult:
    return ValidationResult(
        sql_key=sql_key,
        status="NEED_MORE_PARAMS",
        equivalence={"checked": None, "method": "none", "evidenceRefs": []},
        perf_comparison={"checked": False, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"], "improved": None},
        security_checks={"dollar_substitution_removed": True},
        semantic_risk="medium",
        feedback={"reason_code": "VALIDATE_PARAM_INSUFFICIENT", "message": "db not reachable"},
        selected_candidate_source="rule",
        warnings=[],
        risk_flags=risk_flags,
        decision_layers=_terminal_decision_layers(
            phase="db_unreachable",
            status="NEED_MORE_PARAMS",
            validation_profile=validation_profile,
            feedback_reason_code="VALIDATE_PARAM_INSUFFICIENT",
            reason_codes=["VALIDATE_DB_UNREACHABLE"],
        ),
    )


def build_acceptance_decision(
    equivalence: EquivalenceCheck,
    perf: PerfComparison,
    validation_profile: str,
    rejected_placeholder_semantics: int,
    semantic_equivalence: dict[str, Any] | None = None,
) -> AcceptanceDecision:
    """Build acceptance decision with semantic gate upgrade support.

    Args:
        equivalence: Equivalence check result
        perf: Performance comparison result
        validation_profile: strict/balanced/relaxed
        rejected_placeholder_semantics: Count of rejected placeholder semantics
        semantic_equivalence: Optional semantic equivalence result for gate upgrade

    Returns:
        AcceptanceDecision with determined status
    """
    improved = bool(perf.improved)
    reason_codes = list(perf.reason_codes)
    warnings: list[str] = []
    feedback: dict[str, Any] | None = None
    row_status = (equivalence.row_count or {}).get("status")
    semantic_error = row_status == "ERROR"
    semantic_mismatch = row_status == "MISMATCH"
    semantic_match = row_status == "MATCH"

    if semantic_mismatch:
        status = "FAIL"
        if "VALIDATE_EQUIVALENCE_MISMATCH" not in reason_codes:
            reason_codes.append("VALIDATE_EQUIVALENCE_MISMATCH")
        feedback = {"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH", "message": "semantic mismatch"}
    elif semantic_error:
        status = "NEED_MORE_PARAMS"
        if "VALIDATE_SEMANTIC_ERROR" not in reason_codes:
            reason_codes.append("VALIDATE_SEMANTIC_ERROR")
        feedback = {"reason_code": "VALIDATE_SEMANTIC_ERROR", "message": "semantic check error, manual review required"}
    elif improved:
        status = "PASS"
    elif semantic_match and validation_profile in {"balanced", "relaxed"}:
        status = "PASS"
        warnings.append("VALIDATE_PERF_NOT_IMPROVED_WARN")
        if "VALIDATE_PERF_NOT_IMPROVED_WARN" not in reason_codes:
            reason_codes.append("VALIDATE_PERF_NOT_IMPROVED_WARN")
    else:
        status = "NEED_MORE_PARAMS"
        if "VALIDATE_PERF_NOT_IMPROVED" not in reason_codes:
            reason_codes.append("VALIDATE_PERF_NOT_IMPROVED")
        feedback = {"reason_code": "VALIDATE_PERF_NOT_IMPROVED", "message": "no proven performance gain"}

    # Semantic gate upgrade: if semantic gate passes with sufficient confidence,
    # allow PASS even without performance improvement
    if semantic_equivalence is not None:
        semantic_gate_status = str(semantic_equivalence.get("status") or "PASS").strip().upper()
        semantic_gate_confidence = str(semantic_equivalence.get("confidence") or "HIGH").strip().upper()

        if (
            status != "PASS"
            and semantic_gate_status == "PASS"
            and semantic_gate_confidence in {"MEDIUM", "HIGH"}
        ):
            # Upgrade to PASS
            reason_codes = [
                code for code in reason_codes
                if code.strip().upper() != "VALIDATE_SEMANTIC_ERROR"
            ]
            if status == "NEED_MORE_PARAMS":
                warnings.append("VALIDATE_PERF_NOT_IMPROVED_BUT_SEMANTIC_OK")
            status = "PASS"
            feedback = None

    if rejected_placeholder_semantics:
        warnings.append("VALIDATE_PLACEHOLDER_SEMANTICS_MISMATCH_WARN")

    return AcceptanceDecision(
        status=status,
        feedback=feedback,
        warnings=warnings,
        reason_codes=reason_codes,
    )