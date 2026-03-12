from __future__ import annotations

from typing import Any

from .candidate_generation_models import (
    CandidateGenerationDiagnostics,
    CandidateGenerationOutcome,
    LowValueAssessment,
)
from .candidate_generation_rules import LOW_VALUE_RULES, RECOVERY_RULES
from .candidate_generation_rules.base import CandidateGenerationContext


def _all_text_fallback(raw_candidates: list[dict[str, Any]]) -> bool:
    return bool(raw_candidates) and all(
        str(row.get("rewriteStrategy") or "").strip() == "opencode_text_fallback"
        for row in raw_candidates
    )


def _collect_low_value_assessments(
    context: CandidateGenerationContext,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[LowValueAssessment]]:
    accepted: list[dict[str, Any]] = []
    assessments: list[LowValueAssessment] = []
    for candidate in candidates:
        assessment = None
        for rule in LOW_VALUE_RULES:
            assessment = rule.assess(context, candidate)
            if assessment is not None:
                assessments.append(assessment)
                break
        if assessment is None:
            accepted.append(candidate)
    return accepted, assessments


def evaluate_candidate_generation(
    *,
    sql_key: str,
    original_sql: str,
    sql_unit: dict[str, Any],
    raw_candidates: list[dict[str, Any]],
    valid_candidates: list[dict[str, Any]],
    trace: dict[str, Any],
) -> CandidateGenerationOutcome:
    context = CandidateGenerationContext(
        sql_key=sql_key,
        original_sql=original_sql,
        sql_unit=sql_unit,
        trace=trace,
    )
    accepted_candidates, low_value_assessments = _collect_low_value_assessments(context, valid_candidates)

    diagnostics = CandidateGenerationDiagnostics(
        raw_candidate_count=len(raw_candidates),
        validated_candidate_count=len(valid_candidates),
        accepted_candidate_count=len(accepted_candidates),
        pruned_low_value_count=len(low_value_assessments),
        low_value_candidate_count=len(low_value_assessments),
        raw_rewrite_strategies=[str(row.get("rewriteStrategy") or "") for row in raw_candidates],
        final_candidate_count=len(accepted_candidates),
        low_value_assessments=low_value_assessments,
    )

    degraded_kind: str | None = None
    if _all_text_fallback(raw_candidates):
        degraded_kind = "TEXT_ONLY_FALLBACK"
    elif not valid_candidates:
        degraded_kind = "EMPTY_CANDIDATES"
    elif valid_candidates and not accepted_candidates and low_value_assessments:
        degraded_kind = "ONLY_LOW_VALUE_CANDIDATES"

    diagnostics.degradation_kind = degraded_kind
    if degraded_kind is None:
        diagnostics.recovery_reason = "NONE"
        return CandidateGenerationOutcome(
            accepted_candidates=accepted_candidates,
            recovery_candidates=[],
            diagnostics=diagnostics,
        )

    diagnostics.recovery_attempted = True
    if degraded_kind == "ONLY_LOW_VALUE_CANDIDATES":
        diagnostics.recovery_reason = "LOW_VALUE_PRUNED_TO_EMPTY"
    elif degraded_kind == "EMPTY_CANDIDATES" and str(trace.get("degrade_reason") or "").strip().upper() == "EXECUTION_ERROR":
        diagnostics.recovery_reason = "EXECUTION_ERROR_NO_RECOVERY"
        return CandidateGenerationOutcome(
            accepted_candidates=[],
            recovery_candidates=[],
            diagnostics=diagnostics,
        )

    recovery_candidates: list[dict[str, Any]] = []
    for rule in RECOVERY_RULES:
        recovery = rule.recover(
            context,
            degraded_kind=degraded_kind,
            raw_candidates=raw_candidates,
            accepted_candidates=accepted_candidates,
        )
        if recovery is None:
            continue
        if recovery.reason != "NONE":
            diagnostics.recovery_reason = recovery.reason
        if recovery.strategy:
            diagnostics.recovery_strategy = recovery.strategy
        if recovery.candidates:
            recovery_candidates = recovery.candidates
            break

    if recovery_candidates:
        diagnostics.recovered_candidate_count = len(recovery_candidates)

    return CandidateGenerationOutcome(
        accepted_candidates=accepted_candidates,
        recovery_candidates=recovery_candidates,
        diagnostics=diagnostics,
    )

