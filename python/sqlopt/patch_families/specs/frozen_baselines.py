from __future__ import annotations

from ..models import (
    PatchFamilyAcceptancePolicy,
    PatchFamilyBlockingPolicy,
    PatchFamilyFixtureObligations,
    PatchFamilyPatchTargetPolicy,
    PatchFamilyReplayPolicy,
    PatchFamilyScope,
    PatchFamilySpec,
    PatchFamilyVerificationPolicy,
)

_FROZEN_BASELINE_FAMILIES = (
    "STATIC_STATEMENT_REWRITE",
    "STATIC_WRAPPER_COLLAPSE",
    "STATIC_CTE_INLINE",
    "DYNAMIC_COUNT_WRAPPER_COLLAPSE",
    "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
    "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
    "REDUNDANT_GROUP_BY_WRAPPER",
    "REDUNDANT_HAVING_WRAPPER",
    "REDUNDANT_DISTINCT_WRAPPER",
    "GROUP_BY_FROM_ALIAS_CLEANUP",
    "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP",
    "DISTINCT_FROM_ALIAS_CLEANUP",
)


def _thin_frozen_spec(family: str) -> PatchFamilySpec:
    return PatchFamilySpec(
        family=family,
        status="FROZEN_AUTO_PATCH",
        stage="MVP_SEED",
        scope=PatchFamilyScope(statement_types=("SELECT",), requires_template_preserving=True),
        acceptance=PatchFamilyAcceptancePolicy(
            semantic_required_status="PASS",
            semantic_min_confidence="MEDIUM",
        ),
        patch_target_policy=PatchFamilyPatchTargetPolicy(
            selected_patch_strategy="EXISTING_PIPELINE",
            requires_replay_contract=True,
        ),
        replay=PatchFamilyReplayPolicy(
            required_template_ops=("existing_pipeline",),
            render_mode="EXISTING_PIPELINE",
        ),
        verification=PatchFamilyVerificationPolicy(
            require_replay_match=True,
            require_xml_parse=True,
            require_render_ok=True,
            require_sql_parse=True,
            require_apply_check=True,
        ),
        blockers=PatchFamilyBlockingPolicy(),
        fixture_obligations=PatchFamilyFixtureObligations(
            ready_case_required=True,
            blocked_neighbor_required=False,
            replay_assertions_required=True,
            verification_assertions_required=True,
        ),
    )


FROZEN_BASELINE_SPECS = tuple(_thin_frozen_spec(family) for family in _FROZEN_BASELINE_FAMILIES)
