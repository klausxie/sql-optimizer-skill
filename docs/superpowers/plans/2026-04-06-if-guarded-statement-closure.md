# IF_GUARDED Statement Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `IF_GUARDED_FILTER_STATEMENT` the first fully closed statement family with a stable path from scan to validated patch draft, observable convergence metrics, and CI progress tracking.

**Architecture:** Keep the current pipeline shape. Do not add new stages, branch engines, or solver systems. Tighten only four points: shape identification, validate-time convergence, patch gating/draft consistency, and harness/CI observability. Every iteration must improve one real blocker from run data rather than adding generic infrastructure.

**Tech Stack:** Python, pytest, JSON schema contracts, existing `sqlopt` pipeline, harness runtime/assertions/benchmark, CI helper scripts.

---

## Scope

This plan is intentionally narrow.

In scope:
- `IF_GUARDED_FILTER_STATEMENT`
- `validate -> statement_convergence -> patch_generate`
- harness benchmark and CI observability
- real-run blocker reduction based on `conflictReason`

Out of scope:
- `FOREACH`
- `CHOOSE/WHEN`
- general multi-branch convergence engine
- automatic apply
- new orchestration stages

## Current Baseline

Already in place:
- `statement_convergence.jsonl` artifact
- convergence gating in `patch_generate`
- schema validation for convergence rows
- benchmark snapshot scripts:
  - `scripts/ci/convergence_snapshot.py`
  - `scripts/ci/if_guarded_progress.py`

Current success condition is not "more infrastructure". It is a measurable increase in `AUTO_PATCHABLE` statements for `IF_GUARDED_FILTER_STATEMENT` and a measurable decrease in the top convergence blocker.

## North Star

The project is considered to be moving correctly only when all of the following improve for the targeted statement family:

- `auto_patchable_rate` increases
- `patch_convergence_blocked_count` decreases
- `conflict_reason_counts` become more concentrated and then shrink
- generated patch drafts still pass existing syntax/replay/applicability checks

## Execution Rule

At any point in this plan, only one blocker may be attacked at a time.

Loop:
1. Run real sample-project subset.
2. Measure `IF_GUARDED_FILTER_STATEMENT` progress.
3. Pick top blocker by count.
4. Implement the smallest fix for that blocker.
5. Re-run tests and progress scripts.
6. If metrics do not improve, stop and revise instead of adding more code.

## File Map

Primary product files:
- `python/sqlopt/stages/validate.py`
- `python/sqlopt/stages/patch_generate.py`
- `python/sqlopt/platforms/sql/rewrite_facts.py`
- `python/sqlopt/platforms/sql/patch_safety.py`
- `python/sqlopt/stages/patch_decision/gate_acceptance.py`
- `python/sqlopt/stages/patch_decision/gate_dynamic.py`
- `python/sqlopt/patch_families/specs/dynamic_filter_select_list_cleanup.py`
- `python/sqlopt/patch_families/specs/dynamic_filter_from_alias_cleanup.py`
- `python/sqlopt/patch_families/specs/dynamic_filter_wrapper_collapse.py`

Harness and observability files:
- `python/sqlopt/devtools/harness/assertions/validate.py`
- `python/sqlopt/devtools/harness/benchmark/metrics.py`
- `scripts/ci/convergence_snapshot.py`
- `scripts/ci/if_guarded_progress.py`

Key tests:
- `tests/unit/verification/test_verification_stage_integration.py`
- `tests/unit/patch/test_patch_generate_orchestration.py`
- `tests/unit/patch/test_patch_family_registry.py`
- `tests/unit/patch/test_patch_safety.py`
- `tests/unit/sql/test_rewrite_facts.py`
- `tests/harness/engine/test_harness_validate_assertions.py`
- `tests/harness/fixture/test_fixture_project_patch_report_harness.py`
- `tests/ci/test_convergence_snapshot_script.py`
- `tests/ci/test_if_guarded_progress_script.py`

Real-run inspection targets:
- `tests/fixtures/projects/sample_project/runs/<run_id>/artifacts/statement_convergence.jsonl`
- `tests/fixtures/projects/sample_project/runs/<run_id>/artifacts/patches.jsonl`
- `tests/fixtures/projects/sample_project/runs/<run_id>/artifacts/acceptance.jsonl`

### Task 1: Freeze the Delivery Track

**Files:**
- Modify: `docs/QUICKSTART.md`
- Modify: `docs/current-spec.md`
- Modify: `tests/README.md`
- Test: no new test; docs only

- [ ] **Step 1: Update docs to state the active product track**

Document that the current delivery track is only `IF_GUARDED_FILTER_STATEMENT`, target is validated patch drafts, and `FOREACH` / `CHOOSE` are explicitly deferred.

- [ ] **Step 2: Add the exact progress commands**

Add these commands to the docs:

```bash
python3 scripts/ci/convergence_snapshot.py <run_dir> --format text
python3 scripts/ci/if_guarded_progress.py <run_dir> --mode observe --format text
```

- [ ] **Step 3: Verify documentation references**

Run:

```bash
rg -n "IF_GUARDED_FILTER_STATEMENT|convergence_snapshot|if_guarded_progress" docs tests/README.md
```

Expected: docs point to the same active workflow and do not mention broader dynamic-SQL ambitions as current delivery scope.

### Task 2: Establish a Stable Real-Run Baseline

**Files:**
- Modify: `scripts/run_sample_project.py`
- Modify: `scripts/ci/if_guarded_progress.py`
- Test: `tests/ci/test_run_sample_project_script.py`
- Test: `tests/ci/test_if_guarded_progress_script.py`

- [ ] **Step 1: Add a first-class family-focused run mode**

Ensure `run_sample_project.py` can run a reproducible subset that targets only `IF_GUARDED_FILTER_STATEMENT` candidates. Prefer selection by known mapper paths or curated SQL keys over generic family introspection if that keeps the implementation small.

- [ ] **Step 2: Add a stable text summary**

Make `if_guarded_progress.py` print a short stable summary suitable for human inspection:
- total statements
- auto-patchable rate
- blocked count
- top three conflict reasons

- [ ] **Step 3: Add/update failing tests first**

Run:

```bash
python3 -m pytest tests/ci/test_run_sample_project_script.py tests/ci/test_if_guarded_progress_script.py -q
```

Expected: fail before implementation if new CLI/text behavior is added.

- [ ] **Step 4: Implement minimal support**

Keep it as a wrapper over the existing CLI. Do not introduce a new orchestration path.

- [ ] **Step 5: Re-run tests**

Run:

```bash
python3 -m pytest tests/ci/test_run_sample_project_script.py tests/ci/test_if_guarded_progress_script.py -q
```

Expected: PASS

- [ ] **Step 6: Produce a real baseline**

Run the sample-project subset and capture:
- decision counts
- top conflict reason

This output becomes the baseline for Task 3 onward.

### Task 3: Fix the Top-1 Shape Identification Blocker

**Files:**
- Modify: `python/sqlopt/stages/validate.py`
- Modify: `python/sqlopt/platforms/sql/rewrite_facts.py`
- Modify: `python/sqlopt/devtools/harness/assertions/validate.py`
- Test: `tests/unit/verification/test_verification_stage_integration.py`
- Test: `tests/unit/sql/test_rewrite_facts.py`
- Test: `tests/harness/engine/test_harness_validate_assertions.py`

- [ ] **Step 1: Capture the current blocker from real data**

Run:

```bash
python3 scripts/ci/if_guarded_progress.py <run_dir> --mode observe --format json
```

Expected: identify the top `conflictReason`. If it is not shape recognition related, stop this task and jump to the relevant next task instead of forcing this plan step.

- [ ] **Step 2: Write the failing tests for the smallest missing shape case**

Typical targets:
- missing `shapeFamily`
- inconsistent `shapeFamily`
- `rewriteFacts` absent but template clearly matches IF-guarded filter pattern

- [ ] **Step 3: Implement the smallest inference fix**

Rules:
- prefer deterministic inference from existing `sql_unit` / `templateSql`
- do not add generic branch reasoning
- do not classify other shape families in this task

- [ ] **Step 4: Re-run focused tests**

Run:

```bash
python3 -m pytest tests/unit/verification/test_verification_stage_integration.py tests/unit/sql/test_rewrite_facts.py tests/harness/engine/test_harness_validate_assertions.py -q
```

Expected: PASS

- [ ] **Step 5: Re-run the same real baseline**

Expected: the previous top blocker count drops, or this task is considered unsuccessful.

### Task 4: Fix the Top-1 Convergence Decision Blocker

**Files:**
- Modify: `python/sqlopt/stages/validate.py`
- Modify: `python/sqlopt/stages/patch_decision/gate_acceptance.py`
- Modify: `python/sqlopt/stages/patch_decision/gate_dynamic.py`
- Test: `tests/unit/verification/test_verification_stage_integration.py`
- Test: `tests/unit/patch/test_patch_generate_orchestration.py`
- Test: `tests/unit/patch/test_patch_safety.py`

- [ ] **Step 1: Recompute the top blocker after Task 3**

Only proceed if the new top blocker is convergence-related, such as:
- `PATCH_FAMILY_CONFLICT_OR_MISSING`
- `SEMANTIC_GATE_BLOCKED`
- `CONSENSUS_MISSING`

- [ ] **Step 2: Add one failing test for that exact blocker**

Examples:
- same statement gets compatible patch family but convergence currently blocks
- safe IF-guarded cleanup candidate lacks consensus fingerprint

- [ ] **Step 3: Implement the smallest convergence rule improvement**

Rules:
- no new artifact shape
- no new stage
- no multi-branch framework
- only improve statement-level decision for IF-guarded family

- [ ] **Step 4: Verify patch gating still blocks unsafe cases**

Run:

```bash
python3 -m pytest tests/unit/verification/test_verification_stage_integration.py tests/unit/patch/test_patch_generate_orchestration.py tests/unit/patch/test_patch_safety.py -q
```

Expected: PASS, with blocked unsafe cases preserved.

- [ ] **Step 5: Re-run the real baseline**

Expected: `AUTO_PATCHABLE` count increases without increasing unsafe patch generation.

### Task 5: Harden Patch Draft Quality for the Family

**Files:**
- Modify: `python/sqlopt/patch_families/specs/dynamic_filter_select_list_cleanup.py`
- Modify: `python/sqlopt/patch_families/specs/dynamic_filter_from_alias_cleanup.py`
- Modify: `python/sqlopt/patch_families/specs/dynamic_filter_wrapper_collapse.py`
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`
- Test: `tests/unit/patch/test_patch_family_registry.py`
- Test: `tests/unit/patch/test_patch_safety.py`
- Test: `tests/harness/fixture/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Inspect real AUTO_PATCHABLE rows**

Use the real run to find which patch family is now being selected most often.

- [ ] **Step 2: Write the failing safety/registry test for one real bad draft pattern**

Examples:
- patch family selected but patch surface is wrong
- alias cleanup chosen where wrapper collapse is required

- [ ] **Step 3: Implement the smallest family restriction or preference change**

Rules:
- only touch the active IF-guarded family specs
- do not add a new patch family in this task

- [ ] **Step 4: Re-run focused tests**

Run:

```bash
python3 -m pytest tests/unit/patch/test_patch_family_registry.py tests/unit/patch/test_patch_safety.py tests/harness/fixture/test_fixture_project_patch_report_harness.py -q
```

Expected: PASS

- [ ] **Step 5: Re-run progress measurement**

Expected: patch drafts remain valid while blocker count does not regress.

### Task 6: Convert Observability into a Soft Gate

**Files:**
- Modify: `scripts/ci/if_guarded_progress.py`
- Modify: `scripts/ci/release_acceptance.py`
- Test: `tests/ci/test_if_guarded_progress_script.py`

- [ ] **Step 1: Keep observe mode as the default**

No blocking behavior by default.

- [ ] **Step 2: Add one soft threshold in release acceptance**

Suggested first threshold:
- require the script to run successfully
- print the current `auto_patchable_rate`
- warn but do not fail if below target

- [ ] **Step 3: Add/update tests**

Run:

```bash
python3 -m pytest tests/ci/test_if_guarded_progress_script.py -q
```

Expected: PASS

- [ ] **Step 4: Verify full CI-related commands**

Run:

```bash
python3 scripts/schema_validate_all.py
python3 -m pytest tests/ci -q
```

Expected: PASS

### Task 7: Final Closure Checkpoint

**Files:**
- No required product code changes
- Test: full regression suite

- [ ] **Step 1: Run focused family validation**

Run:

```bash
python3 -m pytest \
  tests/unit/verification/test_verification_stage_integration.py \
  tests/unit/patch/test_patch_generate_orchestration.py \
  tests/unit/patch/test_patch_safety.py \
  tests/harness/engine/test_harness_validate_assertions.py \
  tests/harness/fixture/test_fixture_project_patch_report_harness.py \
  tests/ci/test_convergence_snapshot_script.py \
  tests/ci/test_if_guarded_progress_script.py -q
```

Expected: PASS

- [ ] **Step 2: Run full regression**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS

- [ ] **Step 3: Produce a before/after snapshot**

For the same family-focused run shape, compare:
- `auto_patchable_rate`
- `patch_convergence_blocked_count`
- top `conflictReason`

This is the only acceptable proof that the project moved forward.

## Exit Criteria

This track is complete only when all are true:

- `IF_GUARDED_FILTER_STATEMENT` has a reproducible family-focused run mode
- `statement_convergence` rows are stable and schema-valid
- `AUTO_PATCHABLE` rate improves against the captured baseline
- top blocker count decreases against the captured baseline
- generated patch drafts for the family still satisfy current safety/proof checks
- all focused tests pass
- full `pytest -q` passes

## Stop Conditions

Stop and reassess instead of continuing if any of these happen:

- a proposed fix does not improve the measured top blocker
- a fix improves one metric but breaks patch safety
- work starts drifting into `FOREACH` / `CHOOSE` / generic branch convergence
- more than one blocker is being fixed in the same change

## What Not to Build Next

Do not build these until this plan is complete:

- general multi-branch convergence engine
- agent-based statement solver
- automatic apply for dynamic templates
- generalized dynamic-SQL shape platform
- support expansion to non-IF families

The next valuable move is not more infrastructure. It is making one family visibly better with measured evidence.
