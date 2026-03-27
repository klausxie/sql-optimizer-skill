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


STATIC_WRAPPER_COLLAPSE_SPEC = PatchFamilySpec(
    family="STATIC_WRAPPER_COLLAPSE",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="MEDIUM",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_WRAPPER_COLLAPSE",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
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
