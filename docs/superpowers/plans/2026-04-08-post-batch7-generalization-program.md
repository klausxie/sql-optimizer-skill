# Post-Batch7 Generalization Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue the generalization program after `batch7` by tightening the remaining shared blocker clusters, without reopening family-by-family expansion or widening the deliberately blocked semantic-risk and template-boundary areas.

**Architecture:** Keep the current run/artifact model, `statement_convergence` contract, `generalization_summary.py` view, and blocked-boundary registry unchanged. Treat the system as a blocker-driven program with two active tracks:

1. shared candidate-selection gaps that may still become more precise or safer
2. semantic comparison weaknesses that should become clearer blockers, not hidden as low-value candidate noise

This plan explicitly avoids:
- opening new patch families
- broadening plain `FOREACH/INCLUDE` predicate support
- opening fragment-chain / fragment-choose support
- broadening unsafe `JOIN` / `EXISTS` / `OFFSET -> keyset` semantic rewrites

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture scenarios, candidate-generation engine/support, semantic equivalence, validate convergence, harness fixture tests.

---

## Current Program State

Fresh `batch7` run as of 2026-04-08:

- `generalization-batch7`: `run_c1e7c13a64b4`

Current `batch7` decision view:

- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `patch_convergence_blocked_count = 5`
- `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`
- `recommended_next_step = fix_shared_candidate_selection_gaps`

Per-statement state:

- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_RECOVERY`
- `demo.test.complex.chooseBasic` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseMultipleWhen` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.user.advanced.findUsersByKeyword` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

Interpretation:

- `chooseBasic` and `chooseMultipleWhen` are no longer candidate-selection targets. They are now semantic-risk canaries and must stay blocked.
- `findShipments` is no longer a generic low-value case. It is a clean `NO_SAFE_BASELINE_RECOVERY` sentinel.
- `findUsersByKeyword` remains the strongest live candidate-selection target inside `batch7`.
- `listOrdersWithUsersPaged` has moved out of the low-value bucket and into semantic comparison weakness (`SEMANTIC_PREDICATE_CHANGED`).

---

## Program Strategy

The next stage should not be called “open batch8 family work.” It should be treated as a **post-batch7 blocker program** with three lanes:

1. **Lane A: candidate-selection precision**
   - focus on `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
   - current prime target: `demo.user.advanced.findUsersByKeyword`

2. **Lane B: safe-baseline recovery clarity**
   - focus on `NO_SAFE_BASELINE_RECOVERY`
   - current prime target: `demo.shipment.harness.findShipments`

3. **Lane C: semantic comparison weakness**
   - focus on statements that surfaced `SEMANTIC_PREDICATE_CHANGED`
   - current prime target: `demo.order.harness.listOrdersWithUsersPaged`

This stage is successful if it does **one** of the following safely:
- reduces ambiguity inside one of these lanes
- promotes a statement only if it already fits an existing safe path
- or leaves the statement blocked but with a more honest blocker

This stage is **not** successful if it:
- creates new patch families
- relaxes semantic gates for convenience
- or reclassifies semantic-risk statements into candidate buckets to make the numbers look better

---

## Task 1: Freeze the Post-Batch7 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

- [ ] Add a `POST_BATCH7_SENTINELS` section to the blocker inventory with:
  - `POST_BATCH7_CANDIDATE_TARGETS`
  - `POST_BATCH7_SAFE_BASELINE_SENTINELS`
  - `POST_BATCH7_SEMANTIC_SENTINELS`

- [ ] Record at minimum:
  - `demo.user.advanced.findUsersByKeyword`
  - `demo.shipment.harness.findShipments`
  - `demo.order.harness.listOrdersWithUsersPaged`
  - `demo.test.complex.chooseBasic`
  - `demo.test.complex.chooseMultipleWhen`

- [ ] Extend `generalization_summary.py` so a batch-only run for `generalization-batch7` still exposes:
  - `decision_focus`
  - `recommended_next_step`
  - `ready_regressions`
  - `blocked_boundary_regressions`
  without requiring multi-batch aggregation.

- [ ] Keep the script observational only.

**Success standard:** `generalization_summary.py` can explain the next action from `batch7` alone, without re-reading past notes.

---

## Task 2: Program A — Candidate-Selection Precision for `findUsersByKeyword`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_rules/low_value_speculative.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Lock the current blocker for `demo.user.advanced.findUsersByKeyword` in unit tests and fixture/harness expectations.

- [ ] Inspect the exact remaining candidate pool for this statement and classify each candidate as one of:
  - low-value but structurally safe
  - unsupported strategy
  - semantic-risk rewrite
  - no safe baseline match

- [ ] Only promote the statement if it already fits an existing supported path.
  - No new choose patch family.
  - No generic choose rewrite support.

- [ ] If no safe path exists, make the blocker more honest rather than greener.

**Success standard:** `findUsersByKeyword` ends in one of these states:
- stays `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`, but with cleaner diagnostics
- becomes `NO_SAFE_BASELINE_RECOVERY`
- or becomes ready through an already-supported safe path

Forbidden:
- broad bare-`choose` support
- generic choose template rewrite

---

## Task 3: Program B — Safe-Baseline Recovery Clarity for `findShipments`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/rewrite_facts.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Freeze `demo.shipment.harness.findShipments` as the no-safe-baseline sentinel.

- [ ] Prove whether this statement can map to an already-supported baseline family.
  - If yes, use only that existing family.
  - If no, keep it at `NO_SAFE_BASELINE_RECOVERY`.

- [ ] Add regression tests that `findShipmentsByOrderIds` and other explicit `FOREACH` boundaries do **not** leak into this lane.

**Success standard:** `findShipments` does not regress into a noisier blocker. It either:
- stays `NO_SAFE_BASELINE_RECOVERY`, or
- safely promotes through an existing supported baseline

Forbidden:
- widening plain `FOREACH` predicate support
- inventing a shipment-specific patch family

---

## Task 4: Program C — Semantic Comparison Weakness for `listOrdersWithUsersPaged`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] Freeze `demo.order.harness.listOrdersWithUsersPaged` as the semantic-comparison sentinel.

- [ ] Distinguish whether `SEMANTIC_PREDICATE_CHANGED` is:
  - a true semantic blocker
  - or a comparison weakness caused by formatting / wrapper / harmless predicate normalization

- [ ] Only relax the comparison if the equivalence is already structurally justified and evidence-backed.

- [ ] Explicitly guard:
  - `demo.test.complex.existsSubquery`
  - `demo.test.complex.leftJoinWithNull`
  so that semantic-risk statements do not get weaker blockers as collateral damage.

**Success standard:** `listOrdersWithUsersPaged` becomes either:
- a clearly justified semantic blocker
- or a cleaner candidate-selection / no-safe-baseline blocker
- or ready, but only if current semantics already justify it

Forbidden:
- offset-to-keyset promotion
- broad join semantic relaxation

---

## Task 5: Freeze the Non-Goal Boundary Again

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/scenarios/sample_project.json`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_validate_harness.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/test_fixture_project_patch_report_harness.py`

- [ ] Re-assert exact blockers for non-goals:
  - `demo.order.harness.findOrdersByNos`
  - `demo.shipment.harness.findShipmentsByOrderIds`
  - `demo.test.complex.multiFragmentSeparate`
  - `demo.test.complex.selectWithFragmentChoose`
  - `demo.test.complex.existsSubquery`
  - `demo.test.complex.leftJoinWithNull`
  - `demo.test.complex.chooseWithLimit`

- [ ] Ensure fixture scenario expectations match real harness outputs before each rerun.

**Success standard:** all non-goals remain blocked for the same class of reason, and patch harness continues to report them consistently.

---

## Task 6: Fresh Rerun `batch1..7` and Decide the Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-post-batch7-generalization-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch8-intake.md`

- [ ] Fresh rerun:
  - `generalization-batch1`
  - `generalization-batch2`
  - `generalization-batch3`
  - `generalization-batch4`
  - `generalization-batch5`
  - `generalization-batch6`
  - `generalization-batch7`

- [ ] Use `generalization_summary.py` to produce the whole-program comparison.

- [ ] Record:
  - total ready count
  - top blocker reasons
  - ready regressions
  - blocked boundary regressions
  - decision focus
  - recommended next step

- [ ] Create `generalization-batch8-intake.md` only after the fresh rerun shows which lane is the best next bet:
  - candidate precision
  - safe-baseline recovery
  - or semantic comparison cleanup

**Success standard:** the next batch intake is based on fresh program evidence, not memory.

---

## Verification Commands

Run these at the appropriate checkpoints:

```bash
python3 -m pytest -q tests/ci/test_generalization_summary_script.py

python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/sql/test_candidate_generation_support.py \
  tests/unit/sql/test_semantic_equivalence.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/verification/test_verification_stage_integration.py \
  tests/harness/fixture/test_fixture_project_validate_harness.py \
  tests/harness/fixture/test_fixture_project_patch_report_harness.py

python3 scripts/run_sample_project.py --scope generalization-batch7 --max-steps 0 --max-seconds 240

python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch7=tests/fixtures/projects/sample_project/runs/<fresh-batch7-run> \
  --format text

python3 -m pytest -q
```

---

## Done Criteria

This program is complete when all of the following are true:

1. `batch7` has a stable blocker view and no longer hides semantic-risk and no-safe-baseline statements under a generic low-value bucket.
2. Non-goal boundaries remain blocked and retain their correct blocker class.
3. Fresh `batch1..7` rerun shows:
   - `ready_regressions = 0`
   - `blocked_boundary_regressions = 0`
4. The next stage (`batch8` intake) is chosen from fresh evidence rather than from family backlog pressure.
