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


DYNAMIC_FILTER_WRAPPER_COLLAPSE_SPEC = PatchFamilySpec(
    family="DYNAMIC_FILTER_WRAPPER_COLLAPSE",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_DYNAMIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        dynamic_shape_families=("IF_GUARDED_FILTER_STATEMENT",),
        patch_surface="STATEMENT_BODY",
    ),
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
