# Generalization Batch 7 Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining shared candidate-selection blocker cluster on `generalization-batch7` without widening the deliberate blocked boundaries or relaxing true semantic-risk tails.

**Architecture:** Keep the current run/artifact model, convergence contracts, blocked-boundary registry, and generalization summary view unchanged. Treat `batch7` as a blocker-driven program focused on four candidate-selection targets plus one semantic-risk canary. This plan explicitly avoids opening new patch families or broadening `FOREACH`, fragment-chain, fragment-choose, or semantic-risk support.

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture mappers, candidate-generation engine/support/rules, semantic equivalence, validate convergence, harness scenarios.

---

## Current Batch 7 Intake

Fresh program baseline as of 2026-04-08:

- `generalization-batch1`: `run_a90d09a35501`
- `generalization-batch2`: `run_63fa40d43788`
- `generalization-batch3`: `run_7a429ab21b78`
- `generalization-batch4`: `run_9e0f22aab6fa`
- `generalization-batch5`: `run_8f8c911555db`
- `generalization-batch6`: `run_a0515c9ae14e`

Current decision view:

- `total_statements = 30`
- `AUTO_PATCHABLE = 9`
- `MANUAL_REVIEW = 21`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`

`generalization-batch7` execution pool:

- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.user.advanced.findUsersByKeyword`

Candidate-selection targets inside that pool:

- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.chooseMultipleWhen`
- `demo.user.advanced.findUsersByKeyword`

Semantic-risk canary inside that pool:

- `demo.test.complex.chooseBasic`

Batch7 must keep these statements out of scope:

- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.chooseWithLimit`

---

### Task 1: Freeze the Batch 7 Baseline and Regression View

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Extend the blocker inventory with explicit batch7 target and canary clusters**

Add exact SQL key groupings for the batch7 pool:

```python
BATCH7_CANDIDATE_SELECTION_TARGETS = [
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.shipment.harness.findShipments",
    "demo.test.complex.chooseMultipleWhen",
    "demo.user.advanced.findUsersByKeyword",
]

BATCH7_SEMANTIC_CANARY = [
    "demo.test.complex.chooseBasic",
]
```

- [ ] **Step 2: Add a batch-scoped recommendation for batch7**

`generalization_summary.py` should keep its current whole-program view, but when invoked on only `generalization-batch7` it should still print:

```text
decision_focus=NO_PATCHABLE_CANDIDATE_SELECTED
recommended_next_step=fix_shared_candidate_selection_gaps
```

- [ ] **Step 3: Write or extend the script test**

Cover a batch7-only invocation and assert:
- no crash
- correct batch label
- stable `decision_focus`
- exact `recommended_next_step=fix_shared_candidate_selection_gaps`

Also keep an existing multi-`--batch-run` aggregation path in the same script test file so the batch7 summary change cannot break the whole-program view.

- [ ] **Step 4: Run the script regression slice**

Run:

```bash
python3 -m pytest -q tests/ci/test_generalization_summary_script.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/devtools/generalization_blocker_inventory.py scripts/ci/generalization_summary.py tests/ci/test_generalization_summary_script.py
git commit -m "chore: freeze batch7 blocker inventory"
```


### Task 2: Lock the Batch 7 Regression Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/scenarios/sample_project.json`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_validate_harness.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Add explicit failing tests for the four target statements plus the semantic canary**

Before writing the harness assertions, explicitly edit the source-of-truth fixture rows in `tests/fixtures/scenarios/sample_project.json` so they match the current real program baseline for:
- `demo.shipment.harness.findShipments` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.chooseBasic` -> `VALIDATE_SEMANTIC_ERROR`

Write focused tests for:
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.user.advanced.findUsersByKeyword`

Each test must assert the current blocker exactly:

- `demo.order.harness.listOrdersWithUsersPaged` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.shipment.harness.findShipments` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.chooseBasic` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseMultipleWhen` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.user.advanced.findUsersByKeyword` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

Before locking `demo.shipment.harness.findShipments`, first align the fixture scenario, validate harness, and patch-report harness expectations from the stale `SHAPE_FAMILY_NOT_TARGET` baseline to the current real program baseline `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`. Do not change the target to fit the stale fixture.

```python
assert outcome.diagnostics.recovery_reason == "LOW_VALUE_PRUNED_TO_EMPTY"
```

or at convergence level:

```python
assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY"
```

- [ ] **Step 2: Add guard tests for all explicit non-goals**

Add or extend tests proving these remain blocked:
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.test.complex.chooseWithLimit`

Expected exact blocker reasons:
- `demo.order.harness.findOrdersByNos` -> `SHAPE_FAMILY_NOT_TARGET`
- `demo.shipment.harness.findShipmentsByOrderIds` -> `SHAPE_FAMILY_NOT_TARGET`
- `demo.test.complex.multiFragmentSeparate` -> `SHAPE_FAMILY_NOT_TARGET`
- `demo.test.complex.existsSubquery` -> `SEMANTIC_GATE_BLOCKED`
- `demo.test.complex.leftJoinWithNull` -> `SEMANTIC_GATE_BLOCKED`
- `demo.test.complex.selectWithFragmentChoose` -> `SHAPE_FAMILY_NOT_TARGET`
- `demo.test.complex.chooseWithLimit` -> `SHAPE_FAMILY_NOT_TARGET`

- [ ] **Step 3: Run the focused regression slice**

Run:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/sql/test_candidate_generation_support.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/verification/test_verification_stage_integration.py \
  tests/harness/fixture/test_fixture_project_validate_harness.py \
  tests/harness/fixture/test_fixture_project_patch_report_harness.py
```

Expected: FAIL first, with the batch7 blocker expectations exposed.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/sql/test_candidate_generation_engine.py tests/unit/sql/test_candidate_generation_support.py tests/unit/verification/test_validate_convergence.py tests/unit/verification/test_verification_stage_integration.py tests/fixtures/scenarios/sample_project.json tests/harness/fixture/test_fixture_project_validate_harness.py tests/harness/fixture/test_fixture_project_patch_report_harness.py
git commit -m "test: lock batch7 candidate-selection regressions"
```


### Task 3: Program A — Reduce the Cross-Batch Paged/Join Low-Value Pair

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_rules/low_value_speculative.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] **Step 1: Identify the exact low-value-only pools for the two repeated statements**

Cover:
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`

Assert the real candidate pool shape, including wording drift variants currently seen in runs.

- [ ] **Step 2: Narrowly improve pruning/classification only if the original SQL already matches a known safe baseline**

Allowed:
- more precise low-value classification
- safe baseline recovery when the original SQL already fits an existing supported pattern

Forbidden:
- keyset pagination promotion
- join semantic broadening
- new patch family introduction
- reclassifying either statement into semantic-risk or unsupported-strategy tails just to escape `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

- [ ] **Step 3: Keep the blocked boundary and semantic-risk pair exact**

Explicitly prove:
- `findOrdersByNos`
- `findShipmentsByOrderIds`
- `multiFragmentSeparate`
- `selectWithFragmentChoose`
- `existsSubquery`
- `leftJoinWithNull`

still retain their current exact reason class and do not cross into candidate recovery.

- [ ] **Step 4: Run the paged/join slice**

Run:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/sql/test_candidate_generation_support.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/verification/test_verification_stage_integration.py
```

Expected: PASS, with no new `SHAPE_FAMILY_NOT_TARGET` regressions.

- [ ] **Step 5: Re-run batch7 once**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch7 --max-steps 0 --max-seconds 240
```

Expected:
- either one of the two repeated statements becomes `AUTO_PATCHABLE`
- or both remain blocked under a cleaner, still candidate-selection-focused reason
- neither may move into semantic-risk or unsupported-strategy tails as the “fix”
- `demo.test.complex.chooseMultipleWhen` and `demo.user.advanced.findUsersByKeyword` must remain in candidate-selection blockers during this task
- `demo.test.complex.chooseBasic` must remain `VALIDATE_SEMANTIC_ERROR` during this task

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/candidate_generation_engine.py python/sqlopt/platforms/sql/candidate_generation_support.py python/sqlopt/platforms/sql/candidate_generation_rules/low_value_speculative.py tests/unit/sql/test_candidate_generation_engine.py tests/unit/sql/test_candidate_generation_support.py tests/unit/verification/test_validate_convergence.py tests/unit/verification/test_verification_stage_integration.py
git commit -m "feat: reduce batch7 paged and join candidate blockers"
```


### Task 4: Program B — Reduce the Choose Low-Value Cluster Without Opening Semantic Risk

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_validate_harness.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_patch_report_harness.py`

- [ ] **Step 1: Lock the two choose targets to the candidate-selection lane and keep the semantic canary exact**

Cover:
- `demo.test.complex.chooseMultipleWhen`
- `demo.user.advanced.findUsersByKeyword`

Treat these two as candidate-selection targets only:
- recoverable low-value only
- or still low-value blocked with a more precise candidate-selection reason

Keep:
- `demo.test.complex.chooseBasic` -> `VALIDATE_SEMANTIC_ERROR`

Do not use this task to reclassify the two candidate-selection targets into semantic-risk or unsupported-strategy tails.

- [ ] **Step 2: Improve only comparison weakness, not semantic policy**

Allowed:
- alias-only projection normalization
- select-list cleanup equivalence
- choose-guarded filter cleanup where current shape is already supported

Forbidden:
- allowing `chooseWithLimit`
- allowing fragment choose
- lowering semantic confidence thresholds globally
- moving `chooseMultipleWhen` or `findUsersByKeyword` into semantic-risk or unsupported-strategy buckets as an acceptable end state
- turning `chooseBasic` into a promotion target without a separately proven semantic-safe path

- [ ] **Step 3: Keep the non-goal choose and semantic tails exact**

Prove:
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`

stay blocked for their current exact reason class.

- [ ] **Step 4: Run the choose-focused slice**

Run:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/sql/test_candidate_generation_support.py \
  tests/unit/sql/test_semantic_equivalence.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/harness/fixture/test_fixture_project_validate_harness.py \
  tests/harness/fixture/test_fixture_project_patch_report_harness.py
```

Expected: PASS with choose non-goals still blocked.

- [ ] **Step 5: Re-run batch7 again**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch7 --max-steps 0 --max-seconds 240
```

Expected:
- some choose statements may move to `AUTO_PATCHABLE`
- or the two choose targets remain blocked under a more precise candidate-selection reason
- `chooseBasic` must remain `VALIDATE_SEMANTIC_ERROR` unless the task first adds an explicit semantic-safe proof and corresponding test updates
- non-goal choose and semantic-tail statements remain blocked with the same exact reason class

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/candidate_generation_engine.py python/sqlopt/platforms/sql/candidate_generation_support.py python/sqlopt/platforms/sql/semantic_equivalence.py python/sqlopt/stages/validate_convergence.py tests/unit/sql/test_candidate_generation_engine.py tests/unit/sql/test_semantic_equivalence.py tests/unit/verification/test_validate_convergence.py tests/harness/fixture/test_fixture_project_validate_harness.py tests/harness/fixture/test_fixture_project_patch_report_harness.py
git commit -m "feat: reduce batch7 choose candidate blockers"
```


### Task 5: Fresh Rerun `batch1..7` and Compare the Whole Program

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Re-run the full generalization program**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 480
```

Record the new `batch1..7` run ids.

- [ ] **Step 2: Run the whole-program summary**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=<fresh-run> \
  --batch-run generalization-batch2=<fresh-run> \
  --batch-run generalization-batch3=<fresh-run> \
  --batch-run generalization-batch4=<fresh-run> \
  --batch-run generalization-batch5=<fresh-run> \
  --batch-run generalization-batch6=<fresh-run> \
  --batch-run generalization-batch7=<fresh-run> \
  --format text
```

- [ ] **Step 3: Verify the program gates**

Expected:
- `ready_regressions=0`
- blocked boundaries remain blocked with the same exact reason class
- semantic-risk and unsupported-strategy non-goals remain blocked with the same exact reason class
- `decision_focus` stays singular and clear
- at least one of the four batch7 candidate-selection targets improves from its original exact blocker reason or reaches `AUTO_PATCHABLE`
- otherwise the batch7 program is not complete and must not be closed as success

- [ ] **Step 4: Adjust CI tests only if output shape changes**

Do not widen CI scope otherwise.

- [ ] **Step 5: Run the CI script regressions**

Run:

```bash
python3 -m pytest -q tests/ci/test_generalization_refresh_script.py tests/ci/test_generalization_summary_script.py
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/generalization_refresh.py scripts/ci/generalization_summary.py tests/ci/test_generalization_refresh_script.py tests/ci/test_generalization_summary_script.py
git commit -m "chore: refresh and compare generalization batch7 program"
```


## Success Criteria

Batch7 is considered complete only if all of the following are true:

1. `generalization-batch7` remains runnable from the shared scope registry and CI-covered.
2. Earlier ready statements from `batch1..6` do not regress.
3. At least one of the four batch7 candidate-selection targets improves safely from its original exact blocker reason or becomes `AUTO_PATCHABLE`.
4. `demo.test.complex.chooseBasic` remains a semantic-risk canary blocked as `VALIDATE_SEMANTIC_ERROR`, unless a future plan explicitly expands semantic-safe support for it.
5. Any remaining batch7 candidate-selection targets stay in candidate-selection blockers; they do not “succeed” by being reclassified into semantic-risk or unsupported-strategy tails.
6. The explicit blocked-boundary and semantic-risk non-goal statements remain blocked for the same exact reason class.
7. The whole-program summary still has one clear `decision_focus` after the rerun.
