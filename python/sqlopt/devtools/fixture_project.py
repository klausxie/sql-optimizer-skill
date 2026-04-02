from __future__ import annotations

from pathlib import Path

from sqlopt.devtools.harness.assertions import (
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
from sqlopt.devtools.harness.runtime.project import (
    FIXTURE_CONFIG_DIR,
    FIXTURE_MOCK_DIR,
    FIXTURE_PROJECT_ROOT,
    FIXTURE_SCAN_SAMPLES_DIR,
    FIXTURE_SCENARIOS_PATH,
    FIXTURES_ROOT,
    ROOT,
    copy_fixture_project,
    prepare_fixture_project,
)
from sqlopt.devtools.harness.runtime import (
    run_fixture_patch_and_report_harness,
    run_fixture_validate_harness,
    scan_fixture_project,
    validate_fixture_scenario,
)
from sqlopt.devtools.harness.scenarios import (
    BLOCKER_FAMILIES,
    PATCHABILITY_TARGETS,
    ROADMAP_STAGES,
    ROADMAP_THEMES,
    SCENARIO_CLASSES,
    SEMANTIC_TARGETS,
    VALIDATE_EVIDENCE_MODES,
    VALIDATE_STATUSES,
    load_scenarios,
    summarize_scenarios,
)

load_fixture_scenarios = load_scenarios
summarize_fixture_scenarios = summarize_scenarios


def prepare_mutable_fixture_project(destination_root: Path, *, name: str = "sample_project") -> Path:
    return prepare_fixture_project(destination_root, name=name, mutable=True, init_git=True).root_path
