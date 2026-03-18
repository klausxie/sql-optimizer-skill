from __future__ import annotations

from typing import cast

from .candidate_models import Candidate
from .candidate_patchability_models import (
    CandidatePatchabilityAssessment,
    CandidatePatchabilityContext,
)
from .candidate_patchability_rules import iter_candidate_patchability_rules
from .candidate_patchability_rules.base import CandidatePatchabilityRule


def _patchability_tier(score: int) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def assess_candidate_patchability_model(
    original_sql: str, candidate: Candidate
) -> CandidatePatchabilityAssessment:
    context = CandidatePatchabilityContext(
        original_sql=str(original_sql or ""),
        candidate_source=str(candidate.source or "").strip(),
        rewritten_sql=str(candidate.rewritten_sql or ""),
        rewrite_strategy=str(candidate.rewrite_strategy or "").strip(),
    )
    matches = []
    for registered_rule in iter_candidate_patchability_rules():
        match = cast(
            CandidatePatchabilityRule, registered_rule.implementation
        ).evaluate(context)
        if match is not None:
            matches.append(match)
    score = max(0, min(60 + sum(match.score_delta for match in matches), 100))
    return CandidatePatchabilityAssessment(
        score=score,
        tier=_patchability_tier(score),
        reasons=[match.reason for match in matches],
        matched_rules=matches,
    )


def assess_candidate_patchability(
    original_sql: str, candidate: Candidate
) -> tuple[int, str, list[str]]:
    assessment = assess_candidate_patchability_model(original_sql, candidate)
    return assessment.score, assessment.tier, list(assessment.reasons)
