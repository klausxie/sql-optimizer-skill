from __future__ import annotations

from .fixture_matrix import assert_fixture_scenario_summary
from .helpers import (
    dynamic_blocked_neighbor_families,
    fixture_dynamic_registered_families,
    fixture_registered_blocked_neighbor_families,
    fixture_registered_families,
    patch_apply_ready,
    patch_blocker_family,
    patch_meets_registered_fixture_obligations,
    patchability_bucket,
    primary_blocker,
    registered_patch_family_spec,
    semantic_gate_bucket,
    validate_blocker_family,
)
from .patch import (
    assert_auto_patches_frozen_and_verified,
    assert_patch_matrix_matches_scenarios,
    assert_registered_fixture_patch_obligations,
)
from .report import assert_report_generated
from .run import assert_phase_status, assert_report_rebuild_cleared, assert_run_completed
from .workflow import assert_manifest_contains_stages

__all__ = [
    "assert_auto_patches_frozen_and_verified",
    "assert_fixture_scenario_summary",
    "assert_manifest_contains_stages",
    "assert_patch_matrix_matches_scenarios",
    "assert_phase_status",
    "assert_registered_fixture_patch_obligations",
    "assert_report_generated",
    "assert_report_rebuild_cleared",
    "assert_run_completed",
    "dynamic_blocked_neighbor_families",
    "fixture_dynamic_registered_families",
    "fixture_registered_blocked_neighbor_families",
    "fixture_registered_families",
    "patch_apply_ready",
    "patch_blocker_family",
    "patch_meets_registered_fixture_obligations",
    "patchability_bucket",
    "primary_blocker",
    "registered_patch_family_spec",
    "semantic_gate_bucket",
    "validate_blocker_family",
]
