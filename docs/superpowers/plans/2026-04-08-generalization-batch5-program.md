# Generalization Batch 5 Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the current generalization stabilization loop, turn `generalization-batch5` into a formal runnable batch, and prove or reject the `CHOOSE_GUARDED_FILTER_EXTENSION` path without widening existing blocked boundaries.

**Architecture:** Keep the existing run/artifact model, convergence summaries, and deliberate blocked-boundary registry intact. Extend the generalization program by adding a dedicated `batch5` scope around choose-guarded filter statements, then attack only the minimal shared gaps required for those statements to move from `SHAPE_FAMILY_NOT_TARGET` into either `AUTO_PATCHABLE` or a more precise blocked state. Protect plain `FOREACH/INCLUDE` predicates and ambiguous fragment chains from accidental widening throughout the work.

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_refresh.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture mappers, convergence/validate/candidate-generation layers.

---

### Task 1: Close Task 6 of the Current Stabilization Program

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-stabilization-program.md`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/runs/`

- [ ] **Step 1: Refresh fresh baselines for batches 1-4**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 480
```

Expected: JSON payload with fresh run ids for `generalization-batch1..4`.

- [ ] **Step 2: Capture the refreshed run ids in the stabilization plan**

Append the new run ids under Task 6 notes in:

`docs/superpowers/plans/2026-04-08-generalization-stabilization-program.md`

- [ ] **Step 3: Produce the final four-batch summary**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=<run_dir> \
  --batch-run generalization-batch2=<run_dir> \
  --batch-run generalization-batch3=<run_dir> \
  --batch-run generalization-batch4=<run_dir> \
  --format text
```

Expected: one stable decision view with `decision_focus` and `recommended_next_step`.

- [ ] **Step 4: Check Task 6 exit criteria**

Confirm all of the following from the fresh rerun:
- no previously ready statement regresses
- blocked reasons stay stable
- there is still one clear next blocker focus

- [ ] **Step 5: Mark the old program complete**

Update the old stabilization plan to record Task 6 completion and point to this new batch 5 program as the next stage.


### Task 2: Promote `generalization-batch5` From Candidate Pool to Runnable Scope

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/run_sample_project.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`

- [ ] **Step 1: Add the runnable batch 5 scope**

Promote:

```python
GENERALIZATION_BATCH5_CANDIDATE_SQL_KEYS = (
    "demo.user.advanced.findUsersByKeyword",
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.chooseWithLimit",
    "demo.test.complex.selectWithFragmentChoose",
)
```

into the runnable generalization scope map as `generalization-batch5`.

- [ ] **Step 2: Keep `run_sample_project.py` thin**

Ensure `run_sample_project.py --scope generalization-batch5` works by reusing the shared scope registry, not by adding another bespoke branch.

- [ ] **Step 3: Extend `generalization_refresh.py` to include batch 5**

The refresh script should now run batches `1..5` and return all five run ids.

- [ ] **Step 4: Add CI coverage for batch 5 wiring**

Write script tests that assert:
- `generalization-batch5` is accepted by `run_sample_project.py`
- `generalization_refresh.py` includes batch 5 in output

- [ ] **Step 5: Run batch 5 baseline once**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch5
```

Expected: one fresh run id and a first blocked/ready baseline for the new batch.


### Task 3: Build the Failing Regression Set for `CHOOSE_GUARDED_FILTER_EXTENSION`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/scenarios/sample_project.json`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/src/main/resources/com/example/mapper/user/advanced_user_mapper.xml`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/src/main/resources/com/example/mapper/test/complex_harness_mapper.xml`

- [ ] **Step 1: Lock the five batch 5 statements as explicit regression targets**

Use the real mapper statements and current run baseline, not synthetic placeholders.

- [ ] **Step 2: Write convergence tests for the promote-next path**

Add tests that prove these statements are intentionally in the `CHOOSE_GUARDED_FILTER_EXTENSION` bucket, not accidentally caught by broad family matching.

- [ ] **Step 3: Write regression tests for guarded blocked boundaries**

Protect the existing `keep_blocked` patterns:
- plain `FOREACH + INCLUDE + WHERE`
- ambiguous fragment chains

The tests must fail if batch 5 implementation accidentally promotes them.

- [ ] **Step 4: Add one fixture-level expectation for a still-blocked choose case**

At least one batch 5 statement should remain blocked until candidate/proof work is done, so the batch cannot become “all green by accident”.

- [ ] **Step 5: Run only the new regression subset**

Run:

```bash
python3 -m pytest -q \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/verification/test_verification_stage_integration.py
```

Expected: the new regression coverage passes before implementation continues.


### Task 4: Implement Minimal Batch 5 Capability Without Widening Boundaries

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/convergence_registry.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Add narrow shape support for choose-guarded filter statements**

Only support choose-based dynamic filter statements that are close to the current `IF_GUARDED_FILTER_STATEMENT` family. Do not admit:
- `ORDER BY ${...}` choose branches
- nested fragment chains
- generic choose trees

- [ ] **Step 2: Implement the smallest safe candidate path**

Handle only the batch 5 cluster that can reuse existing safe families, such as:
- select-list alias cleanup
- wrapper collapse
- safe static simplification that preserves the choose subtree

- [ ] **Step 3: Keep speculative rewrites pruned**

Do not let `UNION`, `LIMIT_ADDITION`, `JOIN` expansion, or unsafe reorderings sneak into choose-based templates just because the shape is now targeted.

- [ ] **Step 4: Fix only proven semantic/proof weaknesses**

If a batch 5 statement fails because of comparison weakness, add the minimal equivalence/proof improvement. If it is truly unsafe, keep it blocked with a better raw reason.

- [ ] **Step 5: Re-run batch 5 and inspect all five statements**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch5
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch5=<run_dir> \
  --format text
```

Expected: batch 5 ends in a stable state such as:
- some statements `AUTO_PATCHABLE`
- the rest blocked with precise raw reasons
- no fallback to accidental `SHAPE_FAMILY_NOT_TARGET` for the intended promote-next cluster


### Task 5: Revalidate the Whole Generalization Program Against Batch 5

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-08-generalization-program-view.md`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/runs/`

- [ ] **Step 1: Refresh all five generalization batches**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 600
```

Expected: fresh run ids for batches `1..5`.

- [ ] **Step 2: Extend the summary view to include batch 5**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=<run_dir> \
  --batch-run generalization-batch2=<run_dir> \
  --batch-run generalization-batch3=<run_dir> \
  --batch-run generalization-batch4=<run_dir> \
  --batch-run generalization-batch5=<run_dir> \
  --format text
```

- [ ] **Step 3: Check for regressions in previously ready statements**

Confirm:
- no regression in batches `1..4`
- blocked boundary statements stay blocked for the same reason class

- [ ] **Step 4: Recompute the top blocker focus**

Determine whether the next dominant focus is now:
- `NO_PATCHABLE_CANDIDATE_SELECTED`
- `VALIDATE_STATUS_NOT_PASS`
- `SHAPE_FAMILY_NOT_TARGET`
- or a new concentrated cluster from batch 5

- [ ] **Step 5: Update the summary spec if the decision view changed**

Only update the spec if batch 5 introduces a new stable decision pattern worth keeping.


### Task 6: Freeze the Next Stage Gate and Write the Batch 6 Intake Plan

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch6-intake.md`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch5-program.md`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`

- [ ] **Step 1: Record the final batch 5 outcome**

Summarize:
- which of the five statements became ready
- which remained blocked
- the exact raw blocker reasons

- [ ] **Step 2: Decide whether batch 5 is “done”**

It is done when:
- ready statements are stable on rerun
- blocked statements are intentionally blocked
- there is no accidental widening into the `keep_blocked` boundary set

- [ ] **Step 3: Define the next intake pool**

Pick the next five candidates based on:
- remaining `promote_next` statements
- newly clarified blocker clusters
- not just “more statements from the same mapper”

- [ ] **Step 4: Write the batch 6 intake plan**

Create `docs/superpowers/plans/2026-04-08-generalization-batch6-intake.md` with:
- selected statements
- expected ready/blocked boundary
- blocker hypothesis

- [ ] **Step 5: Run full regression**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS with no regression in previously completed family or generalization work.
