from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "FIXTURES_ROOT": (".project", "FIXTURES_ROOT"),
    "FIXTURE_PROJECT_ROOT": (".project", "FIXTURE_PROJECT_ROOT"),
    "FIXTURE_SCENARIOS_PATH": (".project", "FIXTURE_SCENARIOS_PATH"),
    "FIXTURE_CONFIG_DIR": (".project", "FIXTURE_CONFIG_DIR"),
    "FIXTURE_MOCK_DIR": (".project", "FIXTURE_MOCK_DIR"),
    "FIXTURE_SCAN_SAMPLES_DIR": (".project", "FIXTURE_SCAN_SAMPLES_DIR"),
    "HarnessArtifacts": (".models", "HarnessArtifacts"),
    "HarnessHooks": (".models", "HarnessHooks"),
    "HarnessProjectHandle": (".models", "HarnessProjectHandle"),
    "HarnessRunResult": (".models", "HarnessRunResult"),
    "HarnessStepResult": (".models", "HarnessStepResult"),
    "apply_once": (".runner", "apply_once"),
    "copy_fixture_project": (".project", "copy_fixture_project"),
    "load_run_artifacts": (".artifacts", "load_run_artifacts"),
    "prepare_fixture_project": (".project", "prepare_fixture_project"),
    "resume_once": (".runner", "resume_once"),
    "run_fixture_patch_and_report_harness": (".patch_report_fixture", "run_fixture_patch_and_report_harness"),
    "run_fixture_validate_harness": (".validate_fixture", "run_fixture_validate_harness"),
    "run_once": (".runner", "run_once"),
    "run_until_complete": (".loop", "run_until_complete"),
    "run_until_stage_complete": (".loop", "run_until_stage_complete"),
    "scan_fixture_project": (".scan_fixture", "scan_fixture_project"),
    "status_once": (".runner", "status_once"),
    "validate_fixture_scenario": (".validate_fixture", "validate_fixture_scenario"),
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
