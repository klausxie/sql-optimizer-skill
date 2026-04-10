from __future__ import annotations

from dataclasses import dataclass


PROVIDER_LIMITED_SQL_KEYS = {
    "demo.user.advanced.findUsersByKeyword",
}

DEFERRED_CAPABILITY_REASON_CODES = {
    "NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE",
}

FROZEN_NON_GOAL_REASON_CODES = {
    "NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE",
    "NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY",
    "NO_SAFE_BASELINE_GROUP_BY",
    "NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT",
    "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
}


@dataclass(frozen=True)
class BoundaryPresentation:
    category: str
    summary: str
    recommended_action: str


def _is_supported(decision: str | None) -> bool:
    normalized = str(decision or "").strip().upper()
    return normalized in {"AUTO_PATCHABLE", "READY_TO_APPLY"}


def present_boundary(
    *,
    statement_key: str | None = None,
    blocker_code: str | None = None,
    delivery_decision: str | None = None,
) -> BoundaryPresentation:
    decision = str(delivery_decision or "").strip().upper()
    code = str(blocker_code or "").strip().upper()
    sql_key = str(statement_key or "").strip()

    if _is_supported(decision):
        return BoundaryPresentation(
            category="SUPPORTED",
            summary="supported",
            recommended_action="apply_patch",
        )

    if sql_key in PROVIDER_LIMITED_SQL_KEYS and code == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY":
        return BoundaryPresentation(
            category="PROVIDER_LIMITED",
            summary="blocked by current provider quality",
            recommended_action="consider_provider_investment",
        )

    if code in DEFERRED_CAPABILITY_REASON_CODES:
        return BoundaryPresentation(
            category="DEFERRED_CAPABILITY",
            summary="not supported yet",
            recommended_action="wait_for_future_capability",
        )

    if code.startswith("SEMANTIC_"):
        return BoundaryPresentation(
            category="SEMANTIC_BOUNDARY",
            summary="blocked by semantic safety",
            recommended_action="review_candidate",
        )

    if code.startswith("VALIDATE_"):
        return BoundaryPresentation(
            category="VALIDATE_SECURITY_BOUNDARY",
            summary="blocked by validation/security",
            recommended_action="review_candidate",
        )

    if code.startswith("NO_PATCHABLE_CANDIDATE_UNSUPPORTED_") or code in FROZEN_NON_GOAL_REASON_CODES:
        return BoundaryPresentation(
            category="FROZEN_NON_GOAL",
            summary="not supported in current scope",
            recommended_action="do_not_retry_current_scope",
        )

    return BoundaryPresentation(
        category="OTHER",
        summary="requires manual review",
        recommended_action="review_candidate",
    )
