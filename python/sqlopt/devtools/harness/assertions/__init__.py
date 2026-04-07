from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "assert_auto_patches_frozen_and_verified": (".patch", "assert_auto_patches_frozen_and_verified"),
    "assert_fixture_scenario_summary": (".fixture_matrix", "assert_fixture_scenario_summary"),
    "assert_manifest_contains_stages": (".workflow", "assert_manifest_contains_stages"),
    "assert_patch_matrix_matches_scenarios": (".patch", "assert_patch_matrix_matches_scenarios"),
    "assert_phase_status": (".run", "assert_phase_status"),
    "assert_registered_fixture_patch_obligations": (".patch", "assert_registered_fixture_patch_obligations"),
    "assert_report_generated": (".report", "assert_report_generated"),
    "assert_report_rebuild_cleared": (".run", "assert_report_rebuild_cleared"),
    "assert_run_completed": (".run", "assert_run_completed"),
    "assert_validate_matrix_matches_scenarios": (".validate", "assert_validate_matrix_matches_scenarios"),
    "assert_if_guarded_statement_convergence": (".validate", "assert_if_guarded_statement_convergence"),
    "dynamic_blocked_neighbor_families": (".helpers", "dynamic_blocked_neighbor_families"),
    "fixture_dynamic_registered_families": (".helpers", "fixture_dynamic_registered_families"),
    "fixture_registered_blocked_neighbor_families": (".helpers", "fixture_registered_blocked_neighbor_families"),
    "fixture_registered_families": (".helpers", "fixture_registered_families"),
    "patch_apply_ready": (".helpers", "patch_apply_ready"),
    "patch_blocker_family": (".helpers", "patch_blocker_family"),
    "patch_meets_registered_fixture_obligations": (".helpers", "patch_meets_registered_fixture_obligations"),
    "patchability_bucket": (".helpers", "patchability_bucket"),
    "primary_blocker": (".helpers", "primary_blocker"),
    "registered_patch_family_spec": (".helpers", "registered_patch_family_spec"),
    "semantic_gate_bucket": (".helpers", "semantic_gate_bucket"),
    "validate_blocker_family": (".helpers", "validate_blocker_family"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
