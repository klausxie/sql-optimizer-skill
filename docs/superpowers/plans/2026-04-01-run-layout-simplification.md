# Run Layout Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current layered `runs/<run-id>/` layout with the new minimal `report.json + control/ + artifacts/ + sql/` structure without leaving any legacy dual-write or legacy read paths behind.

**Architecture:** The migration should move all runtime control concerns into `control/`, all direct stage outputs into `artifacts/`, and keep `report.json` as a minimal derived summary only. To preserve `resume` and `apply` after removing `meta.json` and `config.resolved.json`, store run identity/status in `control/state.json` and store the resolved config snapshot inside `control/plan.json`. Report aggregation must stop depending on `run.index.json`, `diagnostics/`, `overview/`, `pipeline/ops/`, and standalone verification ledgers.

**Tech Stack:** Python 3.9, pytest/unittest, JSON schema contracts under `contracts/`, CLI entrypoints in `python/sqlopt/cli.py` and `scripts/sqlopt_cli.py`, fixture runs under `tests/fixtures/project/runs/`

---

## Pre-Checks

- The approved spec is `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-01-run-layout-simplification-design.md`.
- Current public CLI does not expose a `verify` subcommand; `tests/unit/test_cli_help_text.py` asserts that absence. Treat "verify migration" in the spec as internal verification-data ownership migration, not as a request to add a new public command.
- Do not preserve old paths. Delete legacy writes and readers once the new path is in place.

## File Structure Map

**Primary implementation files**

- Modify: `python/sqlopt/run_paths.py`
- Modify: `python/sqlopt/supervisor.py`
- Modify: `python/sqlopt/application/run_repository.py`
- Modify: `python/sqlopt/application/run_service.py`
- Modify: `python/sqlopt/application/run_index.py`
- Modify: `python/sqlopt/application/run_resolution.py`
- Modify: `python/sqlopt/stages/report_loader.py`
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `python/sqlopt/stages/report_writer.py`
- Modify: `python/sqlopt/stages/report_models.py`
- Modify: `python/sqlopt/stages/apply.py`
- Modify: `python/sqlopt/verification/writer.py`
- Modify: `python/sqlopt/stages/scan.py`
- Modify: `python/sqlopt/stages/optimize.py`
- Modify: `python/sqlopt/stages/validate.py`
- Modify: `python/sqlopt/stages/patch_verification.py`
- Modify: `scripts/schema_validate_all.py`

**Likely contract changes**

- Modify: `contracts/run_report.schema.json`
- Modify or delete: `contracts/run_index.schema.json`
- Modify or delete: `contracts/ops_health.schema.json`
- Modify or delete: `contracts/ops_topology.schema.json`
- Modify or delete: `contracts/sql_artifact_index_row.schema.json`
- Modify or delete: `contracts/verification_record.schema.json`
- Modify or delete: `contracts/verification_summary.schema.json`

**Primary tests**

- Create: `tests/unit/test_run_paths.py`
- Modify: `tests/unit/test_run_service.py`
- Modify: `tests/unit/test_status_resolver.py`
- Modify: `tests/unit/test_status_resolver_module.py`
- Modify: `tests/unit/test_cli_run_defaults.py`
- Modify: `tests/unit/test_apply_mode.py`
- Modify: `tests/unit/test_verification_writer.py`
- Modify: `tests/unit/test_verification_stage_integration.py`
- Modify: `tests/unit/test_patch_verification.py`
- Modify: `tests/contract/test_report_builder.py`
- Modify: `tests/contract/test_report_loader.py`
- Modify: `tests/contract/test_report_classification.py`
- Modify: `tests/contract/test_cli_report_finalization.py`
- Modify: `tests/harness/workflow/test_workflow_supervisor.py`
- Modify: `tests/harness/workflow/test_workflow_golden_e2e.py`
- Modify: `tests/ci/test_opencode_smoke_acceptance_script.py`
- Modify: `tests/ci/test_degraded_runtime_acceptance_script.py`
- Modify: `tests/ci/test_release_acceptance_script.py`

**Fixtures and docs**

- Modify: `tests/fixtures/project/runs/...` fixture trees touched by report and workflow tests
- Modify: `docs/QUICKSTART.md`
- Modify: `docs/CONFIG.md`
- Modify: `docs/project/08-artifact-governance.md`
- Modify: `AGENTS.md`

### Task 1: Rebuild the Canonical Run Layout and Control Plane

**Files:**
- Create: `tests/unit/test_run_paths.py`
- Modify: `python/sqlopt/run_paths.py`
- Modify: `python/sqlopt/supervisor.py`
- Modify: `python/sqlopt/application/run_repository.py`
- Modify: `python/sqlopt/application/run_index.py`
- Modify: `python/sqlopt/application/run_resolution.py`
- Modify: `python/sqlopt/application/run_service.py`
- Modify: `tests/unit/test_run_service.py`
- Modify: `tests/harness/workflow/test_workflow_supervisor.py`

- [ ] **Step 1: Write failing path and control-plane tests**

```python
def test_canonical_paths_use_report_control_artifacts_layout():
    paths = canonical_paths(Path("/tmp/run_demo"))
    assert paths.report_json_path == Path("/tmp/run_demo/report.json")
    assert paths.state_path == Path("/tmp/run_demo/control/state.json")
    assert paths.plan_path == Path("/tmp/run_demo/control/plan.json")
    assert paths.manifest_path == Path("/tmp/run_demo/control/manifest.jsonl")
    assert paths.scan_units_path == Path("/tmp/run_demo/artifacts/scan.jsonl")
```

- [ ] **Step 2: Run the focused tests to verify they fail on old paths**

Run: `python3 -m pytest tests/unit/test_run_paths.py tests/unit/test_run_service.py tests/harness/workflow/test_workflow_supervisor.py -v`

Expected: failures mentioning `pipeline/supervisor`, `overview/report.json`, or missing new `control/` / `artifacts/` paths.

- [ ] **Step 3: Implement the new layout primitives and remove `meta.json`**

```python
def report_json_path(self) -> Path:
    return self.run_dir / "report.json"

def control_dir(self) -> Path:
    return self.run_dir / "control"

def artifacts_dir(self) -> Path:
    return self.run_dir / "artifacts"
```

Implementation notes:
- Move `run_id` and current run status into `control/state.json`.
- Store the resolved config snapshot under `control/plan.json`, for example `plan["resolved_config"]`.
- Update run discovery to scan `control/state.json` instead of `pipeline/supervisor/meta.json`.
- Keep `runs/index.json` for root-level run lookup unless you also migrate callers in the same task.

- [ ] **Step 4: Re-run the focused tests and confirm the control plane is stable**

Run: `python3 -m pytest tests/unit/test_run_paths.py tests/unit/test_run_service.py tests/harness/workflow/test_workflow_supervisor.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the control-plane migration**

```bash
git add tests/unit/test_run_paths.py tests/unit/test_run_service.py tests/harness/workflow/test_workflow_supervisor.py python/sqlopt/run_paths.py python/sqlopt/supervisor.py python/sqlopt/application/run_repository.py python/sqlopt/application/run_index.py python/sqlopt/application/run_resolution.py python/sqlopt/application/run_service.py
git commit -m "refactor: migrate run control plane to minimal layout"
```

### Task 2: Collapse Execution History and Stage Outputs into `control/manifest.jsonl` and `artifacts/*.jsonl`

**Files:**
- Modify: `python/sqlopt/supervisor.py`
- Modify: `python/sqlopt/stages/scan.py`
- Modify: `python/sqlopt/stages/optimize.py`
- Modify: `python/sqlopt/stages/validate.py`
- Modify: `python/sqlopt/stages/patch_generate.py`
- Modify: `python/sqlopt/stages/report_loader.py`
- Modify: `scripts/schema_validate_all.py`
- Modify: `tests/contract/test_report_loader.py`
- Modify: `tests/unit/test_verification_stage_integration.py`

- [ ] **Step 1: Write failing loader and validator tests for the new artifact file names**

```python
def test_load_report_inputs_reads_artifacts_layout():
    (run_dir / "artifacts" / "scan.jsonl").write_text('{"sqlKey":"pipeline#1"}\n')
    (run_dir / "control" / "manifest.jsonl").write_text('{"stage":"scan","event":"done","payload":{}}\n')
    inputs = load_report_inputs(run_dir)
    assert inputs.units[0]["sqlKey"] == "pipeline#1"
```

- [ ] **Step 2: Run the focused tests to verify old `pipeline/*` assumptions break**

Run: `python3 -m pytest tests/contract/test_report_loader.py tests/unit/test_verification_stage_integration.py -v`

Expected: failures on `pipeline/scan/sqlunits.jsonl`, `pipeline/manifest.jsonl`, and similar old paths.

- [ ] **Step 3: Update writers and loaders to use only `control/` and `artifacts/`**

```python
append_jsonl(get_run_paths(run_dir).manifest_path, event_row)
write_jsonl(paths.scan_units_path, sql_units)
write_jsonl(paths.proposals_path, proposals)
```

Implementation notes:
- Replace per-phase `supervisor/results/*.jsonl` writes with a single append-only `control/manifest.jsonl`.
- Rename stage output files to `artifacts/scan.jsonl`, `artifacts/fragments.jsonl`, `artifacts/proposals.jsonl`, `artifacts/acceptance.jsonl`, and `artifacts/patches.jsonl`.
- Update `scripts/schema_validate_all.py` to validate the new artifact locations only.

- [ ] **Step 4: Re-run the focused loader and validator tests**

Run: `python3 -m pytest tests/contract/test_report_loader.py tests/unit/test_verification_stage_integration.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the stage-output collapse**

```bash
git add python/sqlopt/supervisor.py python/sqlopt/stages/scan.py python/sqlopt/stages/optimize.py python/sqlopt/stages/validate.py python/sqlopt/stages/patch_generate.py python/sqlopt/stages/report_loader.py scripts/schema_validate_all.py tests/contract/test_report_loader.py tests/unit/test_verification_stage_integration.py
git commit -m "refactor: collapse run event and artifact outputs"
```

### Task 3: Remove Standalone Verification Ledgers and Fold Evidence into Stage Rows

**Files:**
- Modify: `python/sqlopt/verification/writer.py`
- Modify: `python/sqlopt/verification/models.py`
- Modify: `python/sqlopt/stages/optimize.py`
- Modify: `python/sqlopt/stages/validate.py`
- Modify: `python/sqlopt/stages/patch_verification.py`
- Modify: `python/sqlopt/stages/report_loader.py`
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `tests/unit/test_verification_writer.py`
- Modify: `tests/unit/test_patch_verification.py`
- Modify: `tests/contract/test_report_builder.py`

- [ ] **Step 1: Write failing tests that forbid `pipeline/verification/ledger.jsonl`**

```python
def test_validate_writes_verification_fields_into_acceptance_rows():
    rows = read_jsonl(run_dir / "artifacts" / "acceptance.jsonl")
    assert "verification" in rows[0]
    assert not (run_dir / "pipeline" / "verification" / "ledger.jsonl").exists()
```

- [ ] **Step 2: Run the focused verification tests to verify old ledger behavior still exists**

Run: `python3 -m pytest tests/unit/test_verification_writer.py tests/unit/test_patch_verification.py tests/contract/test_report_builder.py -v`

Expected: failures mentioning `pipeline/verification/ledger.jsonl` or `verification_summary`.

- [ ] **Step 3: Replace ledger append logic with row-level evidence embedding**

```python
acceptance_row["verification"] = {
    "status": record.status,
    "reason_code": record.reason_code,
    "checks": payload["checks"],
    "evidence_refs": payload["evidence_refs"],
}
```

Implementation notes:
- Stop writing `pipeline/verification/ledger.jsonl` and `summary.json`.
- Embed validate-proof fields into `artifacts/acceptance.jsonl`.
- Embed patch-proof fields into `artifacts/patches.jsonl`.
- Remove report aggregation dependencies on `verification_rows`; compute summary from acceptance/patch rows instead.
- Delete optimize/scan verification persistence unless a stage artifact truly needs the evidence to remain durable.

- [ ] **Step 4: Re-run the focused verification/report tests**

Run: `python3 -m pytest tests/unit/test_verification_writer.py tests/unit/test_patch_verification.py tests/contract/test_report_builder.py -v`

Expected: PASS with no `pipeline/verification` files created.

- [ ] **Step 5: Commit the verification ownership migration**

```bash
git add python/sqlopt/verification/writer.py python/sqlopt/verification/models.py python/sqlopt/stages/optimize.py python/sqlopt/stages/validate.py python/sqlopt/stages/patch_verification.py python/sqlopt/stages/report_loader.py python/sqlopt/stages/report_builder.py tests/unit/test_verification_writer.py tests/unit/test_patch_verification.py tests/contract/test_report_builder.py
git commit -m "refactor: fold verification evidence into stage artifacts"
```

### Task 4: Shrink the Report Surface to a Minimal `report.json` and Thin SQL Indexes

**Files:**
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `python/sqlopt/stages/report_writer.py`
- Modify: `python/sqlopt/stages/report_models.py`
- Modify: `python/sqlopt/stages/report_render.py`
- Modify: `contracts/run_report.schema.json`
- Modify or delete: `contracts/run_index.schema.json`
- Modify or delete: `contracts/ops_health.schema.json`
- Modify or delete: `contracts/ops_topology.schema.json`
- Modify or delete: `contracts/sql_artifact_index_row.schema.json`
- Modify or delete: `contracts/verification_summary.schema.json`
- Modify: `tests/contract/test_report_builder.py`
- Modify: `tests/contract/test_report_classification.py`

- [ ] **Step 1: Write failing report tests for the reduced summary shape**

```python
def test_report_builder_emits_minimal_report_json():
    payload = artifacts.report.to_contract()
    assert set(payload.keys()) == {
        "run_id", "generated_at", "target_stage", "status",
        "verdict", "next_action", "phase_status", "stats", "blockers",
    }
```

- [ ] **Step 2: Run the report contract tests to verify the current payload is too large**

Run: `python3 -m pytest tests/contract/test_report_builder.py tests/contract/test_report_classification.py -v`

Expected: failures on `overview/report.md`, `run.index.json`, diagnostics lists, or oversized report payload fields.

- [ ] **Step 3: Remove `overview/`, `diagnostics/`, `run.index.json`, and Markdown report generation**

```python
write_json(paths.report_json_path, report_payload)
write_jsonl(run_dir / "sql" / "catalog.jsonl", sql_catalog_rows)
```

Implementation notes:
- Delete `render_report_md` and `render_summary_md` writes from `report_writer.py`.
- Stop building `artifacts.run_index`, `diagnostics_sql_outcomes`, `diagnostics_sql_artifacts`, `diagnostics_blockers_summary`, `topology`, and `health`.
- Keep `sql/catalog.jsonl` but reduce it to the minimal field set from the spec.
- Keep `sql/<sql-key>/index.json` as the per-SQL drill-down entry.

- [ ] **Step 4: Re-run the focused report tests**

Run: `python3 -m pytest tests/contract/test_report_builder.py tests/contract/test_report_classification.py -v`

Expected: PASS, with `report.json` as the only run-level summary file.

- [ ] **Step 5: Commit the report-surface simplification**

```bash
git add python/sqlopt/stages/report_builder.py python/sqlopt/stages/report_writer.py python/sqlopt/stages/report_models.py python/sqlopt/stages/report_render.py contracts/run_report.schema.json contracts/run_index.schema.json contracts/ops_health.schema.json contracts/ops_topology.schema.json contracts/sql_artifact_index_row.schema.json contracts/verification_summary.schema.json tests/contract/test_report_builder.py tests/contract/test_report_classification.py
git commit -m "refactor: reduce run summary to minimal report json"
```

### Task 5: Rewire CLI and Apply/Resume Readers to the New Ownership Rules

**Files:**
- Modify: `python/sqlopt/application/run_service.py`
- Modify: `python/sqlopt/application/status_resolver.py`
- Modify: `python/sqlopt/stages/apply.py`
- Modify: `python/sqlopt/cli.py`
- Modify: `tests/unit/test_cli_run_defaults.py`
- Modify: `tests/unit/test_apply_mode.py`
- Modify: `tests/contract/test_cli_report_finalization.py`

- [ ] **Step 1: Write failing CLI/apply tests that only read new files**

```python
def test_apply_reads_patches_from_artifacts_layout():
    (run_dir / "artifacts" / "patches.jsonl").write_text('{"patchFiles":["/tmp/demo.patch"]}\n')
    state = apply_from_config(run_dir)
    assert state["mode"] == "PATCH_ONLY"
```

- [ ] **Step 2: Run the CLI/apply tests to verify old `config.resolved.json` and `patch_generate` paths still leak through**

Run: `python3 -m pytest tests/unit/test_cli_run_defaults.py tests/unit/test_apply_mode.py tests/contract/test_cli_report_finalization.py -v`

Expected: failures on `overview/config.resolved.json`, `pipeline/patch_generate/patch.results.jsonl`, or stale status/report expectations.

- [ ] **Step 3: Update `resume`, `status`, and `apply` to use `control/` and `artifacts/` only**

```python
config = dict(repository.get_plan().get("resolved_config") or {})
rows = read_jsonl(canonical_paths(run_dir).patches_path)
state = repository.load_state()
```

Implementation notes:
- `resume_run()` should load resolved config from `control/plan.json`.
- `get_status()` should stop depending on removed meta documents.
- `apply_from_config()` should load patch rows from `artifacts/patches.jsonl`.
- `status` output should not reference Markdown reports or diagnostics paths.

- [ ] **Step 4: Re-run the CLI/apply tests**

Run: `python3 -m pytest tests/unit/test_cli_run_defaults.py tests/unit/test_apply_mode.py tests/contract/test_cli_report_finalization.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the reader migration**

```bash
git add python/sqlopt/application/run_service.py python/sqlopt/application/status_resolver.py python/sqlopt/stages/apply.py python/sqlopt/cli.py tests/unit/test_cli_run_defaults.py tests/unit/test_apply_mode.py tests/contract/test_cli_report_finalization.py
git commit -m "refactor: migrate cli readers to minimal run layout"
```

### Task 6: Update Fixtures, Acceptance Coverage, and Documentation to the New Canonical Layout

**Files:**
- Modify: `scripts/ci/degraded_runtime_acceptance.py`
- Modify: `scripts/ci/opencode_smoke_acceptance.py`
- Modify: `scripts/ci/report_rebuild_acceptance.py`
- Modify: `scripts/ci/verification_chain_acceptance.py`
- Modify: `tests/ci/test_degraded_runtime_acceptance_script.py`
- Modify: `tests/ci/test_opencode_smoke_acceptance_script.py`
- Modify: `tests/ci/test_release_acceptance_script.py`
- Modify: `tests/harness/workflow/test_workflow_golden_e2e.py`
- Modify: fixture trees under `tests/fixtures/project/runs/`
- Modify: `docs/QUICKSTART.md`
- Modify: `docs/CONFIG.md`
- Modify: `docs/project/08-artifact-governance.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write failing fixture and acceptance assertions against the new layout**

```python
assert (run_dir / "report.json").exists()
assert (run_dir / "control" / "state.json").exists()
assert (run_dir / "artifacts" / "acceptance.jsonl").exists()
assert not (run_dir / "overview").exists()
assert not (run_dir / "diagnostics").exists()
```

- [ ] **Step 2: Run the workflow and acceptance slice to capture every remaining legacy-path assumption**

Run: `python3 -m pytest tests/harness/workflow/test_workflow_golden_e2e.py tests/ci/test_opencode_smoke_acceptance_script.py tests/ci/test_degraded_runtime_acceptance_script.py tests/ci/test_release_acceptance_script.py -v`

Expected: failures on `overview/`, `pipeline/`, `diagnostics/`, `verification/`, or legacy fixture paths.

- [ ] **Step 3: Update fixtures, CI scripts, and user-facing docs**

```bash
rg -n "overview/|pipeline/|diagnostics/|verification/|run.index.json" docs scripts tests/fixtures tests
```

Implementation notes:
- Rewrite fixture run trees to match the new layout.
- Update acceptance scripts to assert only the new directory structure.
- Remove old examples from `AGENTS.md`, `docs/QUICKSTART.md`, `docs/CONFIG.md`, and `docs/project/08-artifact-governance.md`.

- [ ] **Step 4: Run the focused workflow and acceptance slice again**

Run: `python3 -m pytest tests/harness/workflow/test_workflow_golden_e2e.py tests/ci/test_opencode_smoke_acceptance_script.py tests/ci/test_degraded_runtime_acceptance_script.py tests/ci/test_release_acceptance_script.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the fixture and docs migration**

```bash
git add scripts/ci/degraded_runtime_acceptance.py scripts/ci/opencode_smoke_acceptance.py scripts/ci/report_rebuild_acceptance.py scripts/ci/verification_chain_acceptance.py tests/ci/test_degraded_runtime_acceptance_script.py tests/ci/test_opencode_smoke_acceptance_script.py tests/ci/test_release_acceptance_script.py tests/harness/workflow/test_workflow_golden_e2e.py tests/fixtures/project/runs docs/QUICKSTART.md docs/CONFIG.md docs/project/08-artifact-governance.md AGENTS.md
git commit -m "test: update fixtures and docs for minimal run layout"
```

### Task 7: Run the Final Verification Sweep

**Files:**
- Modify if needed: any files touched above based on final failures

- [ ] **Step 1: Run the core targeted suite**

Run: `python3 -m pytest tests/unit/test_run_paths.py tests/unit/test_run_service.py tests/unit/test_cli_run_defaults.py tests/unit/test_apply_mode.py tests/unit/test_verification_writer.py tests/contract/test_report_loader.py tests/contract/test_report_builder.py tests/harness/workflow/test_workflow_golden_e2e.py -v`

Expected: PASS.

- [ ] **Step 2: Run schema validation against a fresh fixture run**

Run: `python3 scripts/schema_validate_all.py tests/fixtures/project/runs/<updated-run-id>`

Expected: `ok`

- [ ] **Step 3: Run the release acceptance entrypoint**

Run: `python3 scripts/ci/release_acceptance.py`

Expected: zero exit status and no references to removed layout paths.

- [ ] **Step 4: Inspect for legacy path leakage**

Run: `rg -n "overview/|pipeline/supervisor|pipeline/verification|diagnostics/|run.index.json|report.summary.md|report.md" python scripts tests docs contracts`

Expected: no live code paths remain outside historical design docs that are intentionally preserved.

- [ ] **Step 5: Commit the final cleanups**

```bash
git add -A
git commit -m "refactor: finalize minimal run artifact layout"
```

## Notes for the Implementer

1. The biggest hidden dependency is resolved config persistence. Do not delete `config.resolved.json` until `resume_run()` and `apply_from_config()` can read the config snapshot from `control/plan.json`.
2. The second biggest hidden dependency is run discovery. Do not delete `meta.json` path scanning until `run_index.resolve_run_dir()` and `resolve_run_id()` can discover runs from `control/state.json` and `runs/index.json`.
3. Keep `report.json` minimal. If you feel tempted to add a large list back into it, put that data in `sql/` or `artifacts/` instead.
4. Do not introduce compatibility shims that write both old and new paths. The spec explicitly chose a breaking migration.
