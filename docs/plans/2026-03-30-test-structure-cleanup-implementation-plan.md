# Test Structure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `tests/` into stable proof-layer directories without changing runtime behavior.

**Architecture:** Move the existing flat top-level test files into a small set of purpose-based directories: `unit`, `contract`, `harness`, `ci`, and `support`. Keep `tests/fixtures/` unchanged. Update imports and run focused pytest slices after each move group so path changes do not silently break collection.

**Tech Stack:** Pytest, repository-local test helpers, Markdown plan, shell file moves

---

### Task 1: Create the target test directories

**Files:**
- Create: `tests/unit/`
- Create: `tests/contract/`
- Create: `tests/harness/fixture/`
- Create: `tests/harness/workflow/`
- Create: `tests/ci/`
- Create: `tests/support/`

- [ ] **Step 1: Create the new directory tree**

Run: `mkdir -p tests/unit tests/contract tests/harness/fixture tests/harness/workflow tests/ci tests/support`
Expected: directories exist with no test files moved yet.

- [ ] **Step 2: Verify the directory tree**

Run: `find tests -maxdepth 3 -type d | sort`
Expected: the new directories appear under `tests/`.

### Task 2: Move helper and harness tests first

**Files:**
- Modify: `tests/fixture_project_harness_support.py`
- Modify: `tests/test_fixture_project_harness.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`
- Modify: `tests/test_fixture_project_validate_harness.py`
- Create: `tests/support/fixture_project_harness_support.py`
- Create: `tests/harness/fixture/test_fixture_project_harness.py`
- Create: `tests/harness/fixture/test_fixture_project_patch_report_harness.py`
- Create: `tests/harness/fixture/test_fixture_project_validate_harness.py`

- [ ] **Step 1: Move the harness support module**

Run: `mv tests/fixture_project_harness_support.py tests/support/fixture_project_harness_support.py`
Expected: support helper now lives under `tests/support/`.

- [ ] **Step 2: Move fixture harness tests**

Run: `mv tests/test_fixture_project_harness.py tests/harness/fixture/test_fixture_project_harness.py`
Expected: file move succeeds.

Run: `mv tests/test_fixture_project_patch_report_harness.py tests/harness/fixture/test_fixture_project_patch_report_harness.py`
Expected: file move succeeds.

Run: `mv tests/test_fixture_project_validate_harness.py tests/harness/fixture/test_fixture_project_validate_harness.py`
Expected: file move succeeds.

- [ ] **Step 3: Fix helper imports if collection breaks**

Files to inspect:
- `tests/harness/fixture/test_fixture_project_harness.py`
- `tests/harness/fixture/test_fixture_project_patch_report_harness.py`
- `tests/harness/fixture/test_fixture_project_validate_harness.py`

Expected edit: import paths should resolve `tests.support.fixture_project_harness_support`.

- [ ] **Step 4: Run focused harness tests**

Run: `python3 -m pytest -q tests/harness/fixture/test_fixture_project_patch_report_harness.py tests/harness/fixture/test_fixture_project_validate_harness.py`
Expected: tests collect and pass from the new locations.

### Task 3: Move workflow harness tests

**Files:**
- Modify: `tests/test_workflow_engine_orchestration.py`
- Modify: `tests/test_workflow_engine_requests.py`
- Modify: `tests/test_workflow_golden_e2e.py`
- Modify: `tests/test_workflow_supervisor.py`
- Create: `tests/harness/workflow/test_workflow_engine_orchestration.py`
- Create: `tests/harness/workflow/test_workflow_engine_requests.py`
- Create: `tests/harness/workflow/test_workflow_golden_e2e.py`
- Create: `tests/harness/workflow/test_workflow_supervisor.py`

- [ ] **Step 1: Move workflow tests**

Run: `mv tests/test_workflow_engine_orchestration.py tests/harness/workflow/test_workflow_engine_orchestration.py`
Expected: file move succeeds.

Run: `mv tests/test_workflow_engine_requests.py tests/harness/workflow/test_workflow_engine_requests.py`
Expected: file move succeeds.

Run: `mv tests/test_workflow_golden_e2e.py tests/harness/workflow/test_workflow_golden_e2e.py`
Expected: file move succeeds.

Run: `mv tests/test_workflow_supervisor.py tests/harness/workflow/test_workflow_supervisor.py`
Expected: file move succeeds.

- [ ] **Step 2: Run focused workflow collection**

Run: `python3 -m pytest -q tests/harness/workflow/test_workflow_engine_orchestration.py tests/harness/workflow/test_workflow_supervisor.py`
Expected: workflow tests collect and pass from the new locations.

### Task 4: Move CI-facing script tests

**Files:**
- Modify: `tests/test_degraded_runtime_acceptance_script.py`
- Modify: `tests/test_opencode_smoke_acceptance_script.py`
- Modify: `tests/test_release_acceptance_script.py`
- Modify: `tests/test_resolve_run_id_script.py`
- Modify: `tests/test_run_until_budget_script.py`
- Create: `tests/ci/test_degraded_runtime_acceptance_script.py`
- Create: `tests/ci/test_opencode_smoke_acceptance_script.py`
- Create: `tests/ci/test_release_acceptance_script.py`
- Create: `tests/ci/test_resolve_run_id_script.py`
- Create: `tests/ci/test_run_until_budget_script.py`

- [ ] **Step 1: Move CI tests**

Run: `mv tests/test_degraded_runtime_acceptance_script.py tests/ci/test_degraded_runtime_acceptance_script.py`
Expected: file move succeeds.

Run: `mv tests/test_opencode_smoke_acceptance_script.py tests/ci/test_opencode_smoke_acceptance_script.py`
Expected: file move succeeds.

Run: `mv tests/test_release_acceptance_script.py tests/ci/test_release_acceptance_script.py`
Expected: file move succeeds.

Run: `mv tests/test_resolve_run_id_script.py tests/ci/test_resolve_run_id_script.py`
Expected: file move succeeds.

Run: `mv tests/test_run_until_budget_script.py tests/ci/test_run_until_budget_script.py`
Expected: file move succeeds.

- [ ] **Step 2: Run focused CI test slice**

Run: `python3 -m pytest -q tests/ci/test_release_acceptance_script.py tests/ci/test_run_until_budget_script.py`
Expected: tests collect and pass from the new paths.

### Task 5: Move contract tests

**Files:**
- Modify: `tests/test_classification.py`
- Modify: `tests/test_cli_report_finalization.py`
- Modify: `tests/test_contract_model_interfaces.py`
- Modify: `tests/test_contracts_path_resolution.py`
- Modify: `tests/test_failure_classification.py`
- Modify: `tests/test_patch_artifact.py`
- Modify: `tests/test_patch_contracts.py`
- Modify: `tests/test_patch_delivery_semantics.py`
- Modify: `tests/test_reason_codes.py`
- Modify: `tests/test_report_builder.py`
- Modify: `tests/test_report_classification.py`
- Modify: `tests/test_report_loader.py`
- Modify: `tests/test_report_metrics.py`
- Modify: `tests/test_report_topology_schema_compat.py`

- [ ] **Step 1: Move contract tests into `tests/contract/`**

Run: `mv tests/test_classification.py tests/contract/test_classification.py`
Expected: file move succeeds.

Repeat for the remaining contract tests listed above.

- [ ] **Step 2: Run focused contract slice**

Run: `python3 -m pytest -q tests/contract/test_patch_contracts.py tests/contract/test_report_builder.py tests/contract/test_reason_codes.py`
Expected: contract tests collect and pass.

### Task 6: Move remaining top-level tests into `tests/unit/`

**Files:**
- Modify: all remaining `tests/test_*.py` files still at top level after Tasks 2-5

- [ ] **Step 1: List the remaining top-level tests**

Run: `find tests -maxdepth 1 -name 'test_*.py' | sort`
Expected: only unit-scope tests remain.

- [ ] **Step 2: Move the remaining tests into `tests/unit/`**

Run: `find tests -maxdepth 1 -name 'test_*.py' -print0 | xargs -0 -I{} mv '{}' tests/unit/`
Expected: no `test_*.py` files remain at the top of `tests/`.

- [ ] **Step 3: Run a representative unit slice**

Run: `python3 -m pytest -q tests/unit/test_patch_decision_core.py tests/unit/test_patch_family_registry.py tests/unit/test_exists_rewrite.py`
Expected: moved unit tests collect and pass.

### Task 7: Verify the restructured test tree

**Files:**
- Verify only

- [ ] **Step 1: Confirm the new top-level test layout**

Run: `find tests -maxdepth 2 -type d | sort`
Expected: `tests/` now exposes `unit`, `contract`, `harness`, `ci`, `support`, and `fixtures`.

- [ ] **Step 2: Confirm there are no stray top-level test files**

Run: `find tests -maxdepth 1 -name 'test_*.py'`
Expected: no output.

- [ ] **Step 3: Run the core verification slice**

Run: `python3 -m pytest -q tests/harness/fixture/test_fixture_project_patch_report_harness.py tests/unit/test_patch_decision_core.py tests/harness/workflow/test_workflow_engine_orchestration.py`
Expected: the moved harness and unit slices still pass.

- [ ] **Step 4: Commit**

```bash
git add tests docs/plans/2026-03-30-test-structure-cleanup-implementation-plan.md
git commit -m "test: reorganize tests by proof layer"
```
