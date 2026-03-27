# Patch Pipeline Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the patch subsystem as a patch-owned pipeline, remove legacy fallback behavior, and reduce `patch_result` to a thin external artifact.

**Architecture:** First lock the thin `patch_result` contract and convert tests away from public planning payloads. Then internalize `patchTarget` and remove patch-side fallback branches so `patch_generate` only flows through `select -> build -> prove -> finalize`. Finally, migrate all remaining downstream consumers to thin patch outputs plus verification artifacts.

**Tech Stack:** Python 3.9, pytest, JSON schema contracts, existing patch selection/build/proof modules, verification artifacts, run-artifact pipeline under `runs/<run_id>/`

---

## File Map

- `contracts/patch_result.schema.json`
  Public patch artifact schema that must be reduced to thin delivery-facing fields only.
- `python/sqlopt/stages/patching_results.py`
  Current result constructors; likely still central to what gets serialized into `patch_result`.
- `python/sqlopt/stages/patch_finalize.py`
  Should become the single place that assembles thin external patch outputs from internal pipeline state.
- `python/sqlopt/stages/patch_generate.py`
  Thin orchestrator that should stop carrying public/internal boundary leakage.
- `python/sqlopt/stages/patch_proof.py`
  Current proof entry point that still produces `patchTarget`; this is the best place to internalize proof-only models.
- `python/sqlopt/stages/patch_decision_engine.py`
  Must lose all patch-side legacy fallback assumptions.
- `python/sqlopt/stages/patch_decision.py`
  Must stop reading patch-planning data from acceptance and stop assuming public `patchTarget`.
- `python/sqlopt/stages/patch_verification.py`
  Must verify from thin patch outputs plus internal stage context, not acceptance fallback patch payloads.
- `python/sqlopt/patch_contracts.py`
  Must either shrink into an internal helper or stop acting like a public contract source.
- `python/sqlopt/stages/report_builder.py`
  Downstream consumer that must keep working from thin patch outputs.
- `python/sqlopt/stages/report_stats.py`
  Another downstream consumer currently mixing patch and acceptance data; must align with thin outputs.
- `tests/test_patch_contracts.py`
  Must stop asserting public `patchTarget` presence in patch results.
- `tests/test_patch_generate_orchestration.py`
  Main regression suite for the patch-owned pipeline.
- `tests/test_patch_verification.py`
  Must continue proving verification closure without public `patchTarget`.
- `tests/test_patch_applicability.py`
  Must cover new thin-result and no-legacy-fallback behavior.
- `tests/test_fixture_project_patch_report_harness.py`
  Ensures end-to-end fixture patch/report flow survives the thinner contract.
- `tests/test_report_builder.py`
  Guards downstream stats after patch-result slimming.

### Task 1: Thin The Public Patch Result Contract

**Files:**
- Modify: `contracts/patch_result.schema.json`
- Modify: `python/sqlopt/stages/patching_results.py`
- Modify: `python/sqlopt/stages/patch_finalize.py`
- Test: `tests/test_patch_contracts.py`
- Test: `tests/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write the failing contract tests for thin patch results**

Add or update tests to assert that public `patch_result` keeps:

```python
assert set(result.keys()) >= {
    "sqlKey",
    "statementKey",
    "patchFiles",
    "applicable",
    "selectionReason",
    "deliveryOutcome",
}
```

and rejects/removes:

```python
assert "patchTarget" not in result
assert "rewriteMaterialization" not in result
assert "templateRewriteOps" not in result
```

- [ ] **Step 2: Run the focused contract/orchestration tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_contracts.py tests/test_patch_generate_orchestration.py -k 'patch_result or thin'`
Expected: FAIL because the current patch result still exposes internal planning payloads.

- [ ] **Step 3: Reduce `patch_result` schema to delivery-facing fields**

Update `contracts/patch_result.schema.json` so public `patch_result` no longer defines internal planning payloads like:

1. `patchTarget`
2. `rewriteMaterialization`
3. `templateRewriteOps`

Keep only delivery-facing fields and verdict-level proof summaries.

- [ ] **Step 4: Update result constructors to emit thin outputs**

In `python/sqlopt/stages/patching_results.py` and `python/sqlopt/stages/patch_finalize.py`, make the external result constructors produce only the thin public shape. Do not reintroduce internal payloads via a debug envelope.

- [ ] **Step 5: Re-run the focused tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_contracts.py tests/test_patch_generate_orchestration.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add contracts/patch_result.schema.json python/sqlopt/stages/patching_results.py python/sqlopt/stages/patch_finalize.py tests/test_patch_contracts.py tests/test_patch_generate_orchestration.py
git commit -m "refactor: thin patch result contract"
```

### Task 2: Internalize PatchTarget As A Proof-Only Model

**Files:**
- Modify: `python/sqlopt/stages/patch_proof.py`
- Modify: `python/sqlopt/patch_contracts.py`
- Modify: `python/sqlopt/stages/patch_generate.py`
- Test: `tests/test_patch_verification.py`
- Test: `tests/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write the failing proof-path test**

Add a test proving proof still closes even though `patch_result` no longer exports `patchTarget`:

```python
patch_row = execute_one(...)
assert patch_row["replayEvidence"]["matchesTarget"] is True
assert patch_row["syntaxEvidence"]["ok"] is True
assert "patchTarget" not in patch_row
```

- [ ] **Step 2: Run the proof-focused tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_verification.py tests/test_patch_generate_orchestration.py -k 'patchTarget or proof'`
Expected: FAIL because proof currently still pushes `patchTarget` into the public patch result.

- [ ] **Step 3: Convert `patchTarget` to a private proof model**

Change `python/sqlopt/stages/patch_proof.py` so any `patchTarget`-like structure is treated as an internal proof object only. It may still be built internally, but it must not be written into the public patch result.

- [ ] **Step 4: Reduce `patch_contracts.py` to internal helper status**

Either shrink or reorganize `python/sqlopt/patch_contracts.py` so it no longer acts like a public external contract source for downstream consumers.

- [ ] **Step 5: Rewire `patch_generate.py` to keep proof internal**

Ensure `patch_generate.py` carries proof verdicts forward without publishing the internal proof model.

- [ ] **Step 6: Re-run the focused proof tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_verification.py tests/test_patch_generate_orchestration.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python/sqlopt/stages/patch_proof.py python/sqlopt/patch_contracts.py python/sqlopt/stages/patch_generate.py tests/test_patch_verification.py tests/test_patch_generate_orchestration.py
git commit -m "refactor: internalize patch proof target model"
```

### Task 3: Delete Patch-Side Legacy Fallback

**Files:**
- Modify: `python/sqlopt/stages/patch_decision_engine.py`
- Modify: `python/sqlopt/stages/patch_decision.py`
- Modify: `python/sqlopt/stages/patch_verification.py`
- Test: `tests/test_patch_applicability.py`
- Test: `tests/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write failing tests for no-legacy-fallback behavior**

Add or update tests to prove:

1. patch stage no longer reads patch planning from acceptance fallback fields
2. historical patch-planning payloads in acceptance do not drive patch decisions
3. verification uses patch-owned stage data rather than acceptance patch payloads

Example direction:

```python
patch_row = execute_one(sql_unit, thin_acceptance_with_legacy_noise, run_dir, validator)
assert patch_row["selectionReason"]["code"] == expected_from_patch_owned_pipeline
```

- [ ] **Step 2: Run the focused fallback tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_applicability.py tests/test_patch_generate_orchestration.py -k 'legacy or fallback'`
Expected: FAIL because legacy compatibility branches are still present.

- [ ] **Step 3: Remove fallback logic from patch decision modules**

Delete or simplify code paths in:

1. `python/sqlopt/stages/patch_decision_engine.py`
2. `python/sqlopt/stages/patch_decision.py`
3. `python/sqlopt/stages/patch_verification.py`

Rules:

1. do not read patch planning from acceptance
2. do not treat historical public `patchTarget` as part of current pipeline design
3. keep only patch-owned pipeline inputs plus thin external outputs

- [ ] **Step 4: Re-run the focused fallback tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_patch_applicability.py tests/test_patch_generate_orchestration.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/stages/patch_decision_engine.py python/sqlopt/stages/patch_decision.py python/sqlopt/stages/patch_verification.py tests/test_patch_applicability.py tests/test_patch_generate_orchestration.py
git commit -m "refactor: remove patch legacy fallback paths"
```

### Task 4: Migrate Downstream Consumers To Thin Patch Outputs

**Files:**
- Modify: `python/sqlopt/stages/report_builder.py`
- Modify: `python/sqlopt/stages/report_stats.py`
- Modify: `tests/test_fixture_project_patch_report_harness.py`
- Modify: `tests/test_report_builder.py`
- Modify: other targeted tests that still assume public patch planning payloads

- [ ] **Step 1: Write failing downstream tests**

Add or update tests so report and fixture harnesses explicitly prove they work from:

1. thin `patch_result`
2. validate-owned acceptance fields
3. verification artifacts

and do not rely on public patch planning payloads.

- [ ] **Step 2: Run the downstream-focused tests to verify failure**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py`
Expected: FAIL because some downstream logic still assumes public patch-planning detail.

- [ ] **Step 3: Rewire downstream consumers**

Update report and fixture consumers so they compute summaries from:

1. thin patch outputs
2. acceptance `rewriteFacts`
3. verification rows

Do not restore public internal patch payloads just to satisfy consumers.

- [ ] **Step 4: Re-run the downstream tests**

Run: `env PYTHONPATH=python python3 -m pytest -q tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/stages/report_builder.py python/sqlopt/stages/report_stats.py tests/test_fixture_project_patch_report_harness.py tests/test_report_builder.py
git commit -m "refactor: align downstream consumers with thin patch outputs"
```

### Task 5: Full Regression Closure

**Files:**
- Modify: any remaining failing tests discovered in closure
- Verify: full repository regression

- [ ] **Step 1: Run the targeted patch/validate/report regression bundle**

Run:

```bash
env PYTHONPATH=python python3 -m pytest -q \
  tests/test_patch_contracts.py \
  tests/test_patch_generate_orchestration.py \
  tests/test_patch_verification.py \
  tests/test_patch_applicability.py \
  tests/test_fixture_project_patch_report_harness.py \
  tests/test_report_builder.py \
  tests/test_validate_candidate_selection.py \
  tests/test_fixture_project_validate_harness.py
```

Expected: PASS

- [ ] **Step 2: Run full regression**

Run: `env PYTHONPATH=python python3 -m pytest -q`
Expected: PASS across the repository.

- [ ] **Step 3: Commit any final closure fixes**

```bash
git add <remaining files>
git commit -m "test: close patch pipeline finalization regression"
```

- [ ] **Step 4: Record completion notes**

Confirm all completion criteria from the spec:

1. `patch_generate` is a single patch-owned pipeline
2. `patch_result` is thin
3. `patchTarget` is internal-only
4. patch-side legacy fallback is removed
5. downstream consumers no longer depend on internal planning payloads
6. full regression is green
