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


DYNAMIC_FILTER_SELECT_LIST_CLEANUP_SPEC = PatchFamilySpec(
    family="DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_ENVELOPE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        dynamic_shape_families=("IF_GUARDED_FILTER_STATEMENT",),
        forbid_features=("CHOOSE", "BIND", "FOREACH", "SET", "JOIN"),
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="DYNAMIC_STATEMENT_TEMPLATE_EDIT",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=True,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=True,
        require_apply_check=True,
    ),
    blockers=PatchFamilyBlockingPolicy(
        block_on_choose=True,
        block_on_bind=True,
        block_on_foreach=True,
    ),
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=True,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
