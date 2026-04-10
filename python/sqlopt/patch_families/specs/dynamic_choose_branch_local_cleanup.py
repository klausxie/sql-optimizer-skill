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


DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP_SPEC = PatchFamilySpec(
    family="DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_DYNAMIC_LOCAL",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        dynamic_shape_families=("IF_GUARDED_FILTER_STATEMENT",),
        forbid_features=("FOREACH", "SET"),
        patch_surface="CHOOSE_BRANCH_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="EXACT_TEMPLATE_EDIT",
        requires_replay_contract=True,
        materialization_modes=("DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_choose_branch_body",),
        render_mode="DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=True,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=True,
        require_apply_check=True,
    ),
    blockers=PatchFamilyBlockingPolicy(
        block_on_bind=False,
        block_on_choose=False,
        block_on_foreach=False,
    ),
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=True,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
