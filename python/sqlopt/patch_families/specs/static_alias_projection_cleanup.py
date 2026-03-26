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


STATIC_ALIAS_PROJECTION_CLEANUP_SPEC = PatchFamilySpec(
    family="STATIC_ALIAS_PROJECTION_CLEANUP",
    status="REGISTERED_CANDIDATE",
    stage="MVP_TEMPLATE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="EXACT_TEMPLATE_EDIT",
        requires_replay_contract=True,
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="EXACT_TEMPLATE_EDIT",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=True,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=True,
        require_apply_check=True,
    ),
    blockers=PatchFamilyBlockingPolicy(
        block_on_expression_alias=True,
    ),
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=True,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
