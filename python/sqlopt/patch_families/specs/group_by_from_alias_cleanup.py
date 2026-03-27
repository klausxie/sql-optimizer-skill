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


GROUP_BY_FROM_ALIAS_CLEANUP_SPEC = PatchFamilySpec(
    family="GROUP_BY_FROM_ALIAS_CLEANUP",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_AGGREGATION",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        aggregation_shape_families=("GROUP_BY",),
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="MEDIUM",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="EXACT_TEMPLATE_EDIT",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_SQL",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=(),
        render_mode="STATEMENT_SQL",
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
        blocked_neighbor_required=True,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
