# Test Directory Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repository's test layout so test code, fixtures, golden outputs, and local runtime artifacts have clear boundaries without changing test behavior.

**Architecture:** Keep `tests/` focused on executable test code and test helpers, move reusable fixture assets to a top-level `fixtures/` tree, and isolate generated runtime outputs from versioned fixtures. Execute the migration in small batches so path updates and test discovery changes can be verified incrementally.

**Tech Stack:** Python, pytest, shell utilities, git

---

### Task 1: Establish Target Layout And Safety Rails

**Files:**
- Create: `docs/superpowers/plans/2026-04-01-test-directory-reorganization.md`
- Modify: `.gitignore`
- Reference: `tests/`
- Reference: `tests/fixtures/`

- [ ] **Step 1: Confirm the target directory boundaries**

Target structure:

```text
tests/
  ci/
  contract/
  harness/
    fixture/
    workflow/
  support/
  unit/
    application/
    cli/
    configuration/
    llm/
    platforms/
      mysql/
      postgresql/
      sql/
    stages/
    verification/

fixtures/
  project/
    config/
    data/
    scan_samples/
    src/
  sql_local/
  golden_runs/

tmp/
  test_runs/
```

- [ ] **Step 2: Add ignore rules for generated test noise**

Update `.gitignore` to cover:

```gitignore
tests/**/__pycache__/
tests/.DS_Store
tests/**/.DS_Store
tmp/test_runs/
fixtures/project/.opencode-data/
```

- [ ] **Step 3: Record what must remain versioned**

Keep versioned:
- `tests/ci/`
- `tests/contract/`
- `tests/harness/`
- `tests/support/`
- `tests/unit/`
- `fixtures/project/src/`
- `fixtures/project/config/`
- `fixtures/project/data/`
- `fixtures/project/scan_samples/`
- `fixtures/sql_local/`
- minimal `fixtures/golden_runs/`

Do not keep as routine committed state:
- `tests/**/__pycache__`
- `.DS_Store`
- `fixtures/project/.opencode-data/`
- ad hoc run outputs under `tmp/test_runs/`

- [ ] **Step 4: Verify repository is clean before moving files**

Run:

```bash
git status --short
```

Expected: no unexpected modified files before the migration starts.

### Task 2: Remove Generated Noise And Shrink Fixture Bloat

**Files:**
- Delete: `tests/**/__pycache__/*`
- Delete: `tests/.DS_Store`
- Delete: `tests/fixtures/.DS_Store`
- Delete: `tests/fixtures/project/.DS_Store`
- Move or delete: `tests/fixtures/project/.opencode-data/`
- Review then move or delete: `tests/fixtures/project/runs/`

- [ ] **Step 1: Remove Python cache directories**

Run:

```bash
find tests -type d -name __pycache__ -prune -exec rm -rf {} +
```

Expected: no `__pycache__` directories remain under `tests/`.

- [ ] **Step 2: Remove Finder metadata files**

Run:

```bash
find tests -name .DS_Store -delete
```

Expected: no `.DS_Store` files remain under `tests/`.

- [ ] **Step 3: Remove tool cache from versioned fixtures**

Run:

```bash
rm -rf tests/fixtures/project/.opencode-data
```

Expected: fixture size drops substantially and no tests depend on this path.

- [ ] **Step 4: Audit saved run directories and keep only real golden snapshots**

Run:

```bash
find tests/fixtures/project/runs -maxdepth 1 -mindepth 1 -type d | sort
du -sh tests/fixtures/project/runs
```

Expected: decide which run directories are golden evidence worth preserving.

- [ ] **Step 5: Move preserved snapshots to `fixtures/golden_runs/` and delete the rest**

Example:

```bash
mkdir -p fixtures/golden_runs
mv tests/fixtures/project/runs/<kept_run_dir> fixtures/golden_runs/
rm -rf tests/fixtures/project/runs
```

Expected: runtime snapshots are no longer mixed into the live fixture project.

### Task 3: Extract Static Fixtures To A Top-Level `fixtures/` Tree

**Files:**
- Create: `fixtures/project/config/`
- Create: `fixtures/project/data/`
- Create: `fixtures/project/scan_samples/`
- Create: `fixtures/project/src/`
- Create: `fixtures/sql_local/`
- Move: `tests/fixtures/project/sqlopt.yml`
- Move: `tests/fixtures/project/sqlopt.mysql.yml`
- Move: `tests/fixtures/project/sqlopt.mysql.smoke.yml`
- Move: `tests/fixtures/project/sqlopt.scan.local.yml`
- Move: `tests/fixtures/project/fixture_scenarios.json`
- Move: `tests/fixtures/project/llm_response.json`
- Move: `tests/fixtures/project/optimization_candidates.json`
- Move: `tests/fixtures/project/scan_samples/`
- Move: `tests/fixtures/project/src/`
- Move: `tests/fixtures/sql_local/`

- [ ] **Step 1: Create the new fixture directories**

Run:

```bash
mkdir -p fixtures/project/config fixtures/project/data fixtures/project/scan_samples fixtures/project/src fixtures/sql_local fixtures/golden_runs tmp/test_runs
```

Expected: top-level fixture directories exist before file moves.

- [ ] **Step 2: Move config fixtures into `fixtures/project/config/`**

Run:

```bash
mv tests/fixtures/project/sqlopt.yml fixtures/project/config/
mv tests/fixtures/project/sqlopt.mysql.yml fixtures/project/config/
mv tests/fixtures/project/sqlopt.mysql.smoke.yml fixtures/project/config/
mv tests/fixtures/project/sqlopt.scan.local.yml fixtures/project/config/
```

Expected: config assets are separated from source fixtures.

- [ ] **Step 3: Move data fixtures into `fixtures/project/data/`**

Run:

```bash
mv tests/fixtures/project/fixture_scenarios.json fixtures/project/data/
mv tests/fixtures/project/llm_response.json fixtures/project/data/
mv tests/fixtures/project/optimization_candidates.json fixtures/project/data/
```

Expected: static data inputs are grouped together.

- [ ] **Step 4: Move source fixtures and SQL samples**

Run:

```bash
mv tests/fixtures/project/src fixtures/project/
mv tests/fixtures/project/scan_samples fixtures/project/
mv tests/fixtures/sql_local/* fixtures/sql_local/
rmdir tests/fixtures/sql_local
```

Expected: versioned fixture assets are no longer nested under `tests/`.

- [ ] **Step 5: Remove the old empty fixture shell**

Run:

```bash
find tests/fixtures -maxdepth 2 -type f | sort
```

Expected: only intentionally retained compatibility placeholders remain, or the old tree can be removed entirely.

### Task 4: Centralize Fixture Path Resolution

**Files:**
- Modify: `tests/support/fixture_project_harness_support.py`
- Modify: `tests/harness/fixture/test_fixture_project_harness.py`
- Modify: `tests/harness/fixture/test_fixture_project_patch_report_harness.py`
- Modify: `tests/harness/fixture/test_fixture_project_validate_harness.py`
- Modify: `tests/harness/workflow/test_workflow_golden_e2e.py`

- [ ] **Step 1: Add one shared fixture root constant**

Use:

```python
ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = ROOT / "fixtures"
FIXTURE_PROJECT = FIXTURES_ROOT / "project"
```

Expected: fixture location only needs to change in one place later.

- [ ] **Step 2: Update config and data references to new paths**

Examples:

```python
SCENARIO_MATRIX = FIXTURE_PROJECT / "data" / "fixture_scenarios.json"
CONFIG_SQL_OPT = FIXTURE_PROJECT / "config" / "sqlopt.yml"
```

Expected: tests stop depending on `tests/fixtures/project/...`.

- [ ] **Step 3: Update any run-output expectations to use `fixtures/golden_runs/` or `tmp/test_runs/`**

Expected: preserved golden snapshots are read from a stable path and ad hoc run output is written outside versioned fixtures.

- [ ] **Step 4: Run only the harness tests that exercise fixture path usage**

Run:

```bash
python3 -m pytest tests/harness/fixture -q
python3 -m pytest tests/harness/workflow/test_workflow_golden_e2e.py -q
```

Expected: fixture-dependent harness tests pass after the path rewrite.

### Task 5: Split `tests/unit/` By Runtime Ownership

**Files:**
- Create: `tests/unit/application/`
- Create: `tests/unit/cli/`
- Create: `tests/unit/configuration/`
- Create: `tests/unit/llm/`
- Create: `tests/unit/platforms/mysql/`
- Create: `tests/unit/platforms/postgresql/`
- Create: `tests/unit/platforms/sql/`
- Create: `tests/unit/stages/`
- Create: `tests/unit/verification/`
- Move: flat files from `tests/unit/*.py` into the above directories

- [ ] **Step 1: Create the destination directories**

Run:

```bash
mkdir -p tests/unit/application tests/unit/cli tests/unit/configuration tests/unit/llm tests/unit/platforms/mysql tests/unit/platforms/postgresql tests/unit/platforms/sql tests/unit/stages tests/unit/verification
```

Expected: destination tree is ready before moves.

- [ ] **Step 2: Move application-oriented tests**

Move:

```text
tests/unit/test_run_service.py -> tests/unit/application/test_run_service.py
tests/unit/test_run_index_cache.py -> tests/unit/application/test_run_index_cache.py
tests/unit/test_run_index_resolution.py -> tests/unit/application/test_run_index_resolution.py
tests/unit/test_lifecycle_policy.py -> tests/unit/application/test_lifecycle_policy.py
tests/unit/test_finalizer_module.py -> tests/unit/application/test_finalizer.py
tests/unit/test_action_guidance_consistency.py -> tests/unit/application/test_diagnostics_summary_action_guidance.py
tests/unit/test_output_guidance_consistency.py -> tests/unit/application/test_diagnostics_summary_output_guidance.py
tests/unit/test_status_resolver.py -> tests/unit/application/test_status_resolver.py
tests/unit/test_status_resolver_module.py -> tests/unit/application/test_status_resolver_module.py
```

- [ ] **Step 3: Move CLI, configuration, and LLM tests**

Move:

```text
tests/unit/test_cli_help_text.py -> tests/unit/cli/test_help_text.py
tests/unit/test_cli_run_defaults.py -> tests/unit/cli/test_run_defaults.py

tests/unit/test_config_auto_injected_sections.py -> tests/unit/configuration/test_auto_injected_sections.py
tests/unit/test_config_defaults.py -> tests/unit/configuration/test_defaults.py
tests/unit/test_config_removed_keys.py -> tests/unit/configuration/test_removed_keys.py
tests/unit/test_config_service.py -> tests/unit/configuration/test_service.py
tests/unit/test_config_validation.py -> tests/unit/configuration/test_validation.py
tests/unit/test_config_versioning.py -> tests/unit/configuration/test_versioning.py

tests/unit/test_llm_direct_provider.py -> tests/unit/llm/test_direct_provider.py
tests/unit/test_llm_opencode_provider.py -> tests/unit/llm/test_opencode_provider.py
tests/unit/test_llm_output_validator.py -> tests/unit/llm/test_output_validator.py
tests/unit/test_llm_retry.py -> tests/unit/llm/test_retry_context.py
tests/unit/test_llm_strict_failure.py -> tests/unit/llm/test_strict_failure.py
```

- [ ] **Step 4: Move stage and verification tests**

Move:

```text
tests/unit/test_preflight_stage.py -> tests/unit/stages/test_preflight.py
tests/unit/test_scan_stage.py -> tests/unit/stages/test_scan.py
tests/unit/test_apply_mode.py -> tests/unit/stages/test_apply.py
tests/unit/test_patch_generate_orchestration.py -> tests/unit/stages/test_patch_generate_orchestration.py
tests/unit/test_patch_generate_llm.py -> tests/unit/stages/test_patch_generate_llm.py
tests/unit/test_llm_feedback.py -> tests/unit/stages/test_llm_feedback.py
tests/unit/test_runtime_retry.py -> tests/unit/stages/test_runtime_retry.py

tests/unit/test_verification_writer.py -> tests/unit/verification/test_writer.py
tests/unit/test_verification_stage_integration.py -> tests/unit/verification/test_stage_integration.py
```

- [ ] **Step 5: Move platform tests**

Move:

```text
tests/unit/test_mysql_compare.py -> tests/unit/platforms/mysql/test_compare.py
tests/unit/test_mysql_compat.py -> tests/unit/platforms/mysql/test_compat.py
tests/unit/test_mysql_evidence.py -> tests/unit/platforms/mysql/test_evidence.py
tests/unit/test_compare_prepare.py -> tests/unit/platforms/postgresql/test_compare_prepare.py

tests/unit/test_acceptance_policy.py -> tests/unit/platforms/sql/test_acceptance_policy.py
tests/unit/test_candidate_patchability.py -> tests/unit/platforms/sql/test_candidate_patchability.py
tests/unit/test_candidate_selection_models.py -> tests/unit/platforms/sql/test_candidate_selection_models.py
tests/unit/test_candidate_selection_module.py -> tests/unit/platforms/sql/test_candidate_selection.py
tests/unit/test_canonicalization.py -> tests/unit/platforms/sql/test_canonicalization.py
tests/unit/test_dynamic_candidate_intent.py -> tests/unit/platforms/sql/test_dynamic_candidate_intent.py
tests/unit/test_exists_rewrite.py -> tests/unit/platforms/sql/test_exists_rewrite.py
tests/unit/test_join_consolidation.py -> tests/unit/platforms/sql/test_join_consolidation.py
tests/unit/test_join_elimination.py -> tests/unit/platforms/sql/test_join_elimination.py
tests/unit/test_join_left_to_inner.py -> tests/unit/platforms/sql/test_join_left_to_inner.py
tests/unit/test_join_reordering.py -> tests/unit/platforms/sql/test_join_reordering.py
tests/unit/test_optimize_proposal.py -> tests/unit/platforms/sql/test_optimizer_sql.py
tests/unit/test_patch_decision_core.py -> tests/unit/platforms/sql/test_patch_decision_core.py
tests/unit/test_patch_decision_gates.py -> tests/unit/platforms/sql/test_patch_decision_gates.py
tests/unit/test_patch_family_registry.py -> tests/unit/platforms/sql/test_patch_family_registry.py
tests/unit/test_patch_formatting.py -> tests/unit/platforms/sql/test_patch_formatting.py
tests/unit/test_patch_replay.py -> tests/unit/platforms/sql/test_patch_replay.py
tests/unit/test_patch_safety.py -> tests/unit/platforms/sql/test_patch_safety.py
tests/unit/test_patch_strategy_planner.py -> tests/unit/platforms/sql/test_patch_strategy_planner.py
tests/unit/test_patch_syntax.py -> tests/unit/platforms/sql/test_patch_syntax.py
tests/unit/test_patch_verification.py -> tests/unit/platforms/sql/test_patch_verification.py
tests/unit/test_patching_render.py -> tests/unit/platforms/sql/test_patching_render.py
tests/unit/test_patching_results.py -> tests/unit/platforms/sql/test_patching_results.py
tests/unit/test_patching_templates.py -> tests/unit/platforms/sql/test_patching_templates.py
tests/unit/test_rewrite_facts.py -> tests/unit/platforms/sql/test_rewrite_facts.py
tests/unit/test_semantic_equivalence.py -> tests/unit/platforms/sql/test_semantic_equivalence.py
tests/unit/test_template_materialization.py -> tests/unit/platforms/sql/test_template_materialization.py
tests/unit/test_template_rendering.py -> tests/unit/platforms/sql/test_template_rendering.py
tests/unit/test_union_collapse.py -> tests/unit/platforms/sql/test_union_collapse.py
tests/unit/test_union_collapse_strategy.py -> tests/unit/platforms/sql/test_union_collapse_strategy.py
tests/unit/test_validate_candidate_selection.py -> tests/unit/platforms/sql/test_validate_candidate_selection.py
tests/unit/test_validate_profiles.py -> tests/unit/platforms/sql/test_validate_profiles.py
tests/unit/test_validation_strategy.py -> tests/unit/platforms/sql/test_validation_strategy.py
tests/unit/test_llm_semantic_check.py -> tests/unit/platforms/sql/test_llm_semantic_check.py
tests/unit/test_platform_adapter_compat.py -> tests/unit/platforms/test_adapter_compat.py
tests/unit/test_platform_dispatch.py -> tests/unit/platforms/test_dispatch.py
tests/unit/test_build_bundle.py -> tests/unit/platforms/test_build_bundle.py
tests/unit/test_run_paths.py -> tests/unit/platforms/test_run_paths.py
tests/unit/test_schema_validate_all.py -> tests/unit/platforms/test_schema_validate_all.py
```

- [ ] **Step 6: Run the whole unit tree after each move batch**

Run:

```bash
python3 -m pytest tests/unit/application -q
python3 -m pytest tests/unit/configuration tests/unit/cli tests/unit/llm -q
python3 -m pytest tests/unit/stages tests/unit/verification -q
python3 -m pytest tests/unit/platforms -q
```

Expected: failures, if any, are isolated to the batch just moved.

### Task 6: Reconfirm `contract`, `ci`, and `harness` Boundaries

**Files:**
- Review: `tests/contract/*.py`
- Review: `tests/ci/*.py`
- Review: `tests/harness/**/*.py`

- [ ] **Step 1: Keep `contract/` limited to exported schemas and artifact semantics**

Leave in `tests/contract/`:
- `test_patch_artifact.py`
- `test_patch_contracts.py`
- `test_patch_delivery_semantics.py`
- `test_report_builder.py`
- `test_report_loader.py`
- `test_report_metrics.py`
- `test_report_topology_schema_compat.py`
- `test_contract_model_interfaces.py`
- `test_contracts_path_resolution.py`
- `test_reason_codes.py`
- `test_classification.py`
- `test_failure_classification.py`
- `test_report_classification.py`
- `test_cli_report_finalization.py`

- [ ] **Step 2: Keep `ci/` limited to script entrypoints and acceptance wrappers**

Expected: no pure module unit tests migrate into `tests/ci/`.

- [ ] **Step 3: Keep `harness/` limited to multi-component workflow and fixture-driven tests**

Expected: cross-stage or fixture-heavy tests stay in `tests/harness/`.

- [ ] **Step 4: Run these directories explicitly**

Run:

```bash
python3 -m pytest tests/contract -q
python3 -m pytest tests/ci -q
python3 -m pytest tests/harness -q
```

Expected: each responsibility bucket passes independently.

### Task 7: Final Verification And Cleanup

**Files:**
- Review: `tests/`
- Review: `fixtures/`
- Review: `.gitignore`

- [ ] **Step 1: Confirm no stale paths still reference `tests/fixtures`**

Run:

```bash
rg "tests/fixtures" tests python scripts docs
```

Expected: no remaining hard-coded references, or only deliberate compatibility notes.

- [ ] **Step 2: Confirm no generated noise remains**

Run:

```bash
find tests -name __pycache__ -o -name .DS_Store
```

Expected: no output.

- [ ] **Step 3: Run the full test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: baseline suite passes, or any pre-existing failures are documented explicitly.

- [ ] **Step 4: Summarize the migration in one commit**

Run:

```bash
git status --short
git add .gitignore tests fixtures docs/superpowers/plans/2026-04-01-test-directory-reorganization.md
git commit -m "test: reorganize test directories and fixtures"
```

Expected: one reviewable commit with only test-layout and fixture-path changes.
