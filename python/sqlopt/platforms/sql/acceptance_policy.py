from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcceptanceDecision:
    status: str
    feedback: dict[str, Any] | None
    warnings: list[str]
    reason_codes: list[str]


def security_failure_result(sql_key: str, validation_profile: str, risk_flags: list[str]) -> dict[str, Any]:
    status = "FAIL" if validation_profile == "strict" else "NEED_MORE_PARAMS"
    return {
        "sqlKey": sql_key,
        "status": status,
        "equivalence": {"checked": True, "method": "static", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": False},
        "semanticRisk": "high",
        "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", "message": "unsafe ${} pattern"},
        "selectedCandidateSource": "rule",
        "warnings": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"] if status != "FAIL" else [],
        "riskFlags": risk_flags,
    }


def invalid_candidate_result(sql_key: str, risk_flags: list[str]) -> dict[str, Any]:
    return {
        "sqlKey": sql_key,
        "status": "FAIL",
        "equivalence": {"checked": True, "method": "candidate_sanity", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_EQUIVALENCE_MISMATCH"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": False},
        "semanticRisk": "high",
        "feedback": {"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH", "message": "invalid candidate sql"},
        "selectedCandidateSource": "llm",
        "warnings": [],
        "riskFlags": risk_flags,
    }


def db_unreachable_result(sql_key: str, risk_flags: list[str]) -> dict[str, Any]:
    return {
        "sqlKey": sql_key,
        "status": "NEED_MORE_PARAMS",
        "equivalence": {"checked": None, "method": "none", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": True},
        "semanticRisk": "medium",
        "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT", "message": "db not reachable"},
        "selectedCandidateSource": "rule",
        "warnings": [],
        "riskFlags": risk_flags,
    }


def build_acceptance_decision(
    equivalence: dict[str, Any],
    perf: dict[str, Any],
    validation_profile: str,
    rejected_placeholder_semantics: int,
) -> AcceptanceDecision:
    improved = bool(perf.get("improved"))
    reason_codes = list(perf.get("reasonCodes") or [])
    warnings: list[str] = []
    feedback: dict[str, Any] | None = None
    row_status = ((equivalence.get("rowCount") or {}) if isinstance(equivalence, dict) else {}).get("status")
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

    if rejected_placeholder_semantics:
        warnings.append("VALIDATE_PLACEHOLDER_SEMANTICS_MISMATCH_WARN")

    return AcceptanceDecision(
        status=status,
        feedback=feedback,
        warnings=warnings,
        reason_codes=reason_codes,
    )
