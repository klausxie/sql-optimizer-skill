# Generalization Stabilization Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shift the project from family-by-family expansion into a blocker-driven generalization program that proves which existing capabilities really hold on broader `sample_project` statements, and fixes the highest-value shared blockers before opening more families.

**Architecture:** Keep the current run/artifact model and family convergence layer intact. Build a repeatable loop around `sample_project` generalization batches: refresh baselines, summarize outcomes, attack the top shared blockers (`NO_PATCHABLE_CANDIDATE_SELECTED`, `SEMANTIC_GATE_NOT_PASS`, `VALIDATE_STATUS_NOT_PASS`), and only then open additional batches. Avoid widening blocked families by accident.

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture mappers, convergence/validate/candidate-generation layers.

---

### Task 1: Freeze a Fresh Generalization Baseline for Batches 1-4

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/run_sample_project.py`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Add a dedicated batch refresh entrypoint**

Create `scripts/ci/generalization_refresh.py` that runs `generalization-batch1` through `generalization-batch4`, captures the new run ids, and prints a stable JSON payload:

```json
{
  "batches": {
    "generalization-batch1": "run_xxx",
    "generalization-batch2": "run_yyy"
  }
}
```

- [ ] **Step 2: Keep scope ownership in one place**

Do not move batch SQL-key ownership out of `sample_project_family_scopes.py`. The refresh script should import:

```python
from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS
```

and never duplicate the batch definitions.

- [ ] **Step 3: Add CI coverage for the refresh script shape**

Write a script test that asserts:
- each known batch name is accepted
- output contains all requested batch names
- no family scopes outside `generalization-batch1..4` are required to use the script

- [ ] **Step 4: Re-run all four batches fresh**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 480
```

Expected: one fresh run id per batch.

- [ ] **Step 5: Save the baseline ids in the task notes**

Record the four fresh run ids in the task PR/notes so later summary commands and reviews do not depend on stale or deleted run directories.

Fresh baseline ids recorded on 2026-04-08:
- `generalization-batch1`: `run_37b482a6c0ce`
- `generalization-batch2`: `run_6b0277d6f90f`
- `generalization-batch3`: `run_87e36424c84e`
- `generalization-batch4`: `run_92d4ba2ad30f`


### Task 2: Turn Generalization Summary Into the Primary Product View

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/run_progress_summary.py`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-08-generalization-program-view.md`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Add overall ready/blocked metrics**

Extend the summary payload with:

```json
{
  "overall": {
    "auto_patchable_rate": 0.20,
    "blocked_statement_count": 12
  }
}
```

- [ ] **Step 2: Add blocker bucket grouping**

Group raw conflict reasons into a small stable set for decisions:
- `NO_PATCHABLE_CANDIDATE_SELECTED`
- `SEMANTIC_GATE_NOT_PASS`
- `VALIDATE_STATUS_NOT_PASS`
- `SHAPE_FAMILY_NOT_TARGET`
- `OTHER`

The summary should include both raw counts and grouped counts.

- [ ] **Step 3: Keep statement-level detail intact**

Do not remove statement rows. The command must still answer:
- which statement is ready
- which statement is blocked
- why it is blocked
- whether a patch file exists

- [ ] **Step 4: Add a short human-readable decision view**

`--format text` should end with a short conclusion block, for example:

```text
decision_focus=NO_PATCHABLE_CANDIDATE_SELECTED
recommended_next_step=fix_shared_candidate_selection_gaps
```

- [ ] **Step 5: Run the summary against the fresh four-batch baseline**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=<run_dir> \
  --batch-run generalization-batch2=<run_dir> \
  --batch-run generalization-batch3=<run_dir> \
  --batch-run generalization-batch4=<run_dir> \
  --format text
```

Expected: a single view you can use for project decisions without opening individual run directories.


### Task 3: Attack Shared Blocker Program A — `NO_PATCHABLE_CANDIDATE_SELECTED`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Build a failing regression set from current blocked statements**

Use the fresh batch summary to pick the concrete blocked statements currently under `NO_PATCHABLE_CANDIDATE_SELECTED`, then encode them as targeted regressions in unit tests or fixture-driven tests.

- [ ] **Step 2: Separate “truly no candidate” from “candidate wording drift”**

Any case where the selected candidate exists but convergence misses it because of wording should be fixed in convergence mapping, not left as no-candidate.

- [ ] **Step 3: Separate “unsafe candidate pruned” from “safe baseline missing”**

Candidate-generation code should explain whether a statement is blocked because:
- speculative candidates were correctly rejected
- or a safe recovery path is missing

Use diagnostics and tests to lock this distinction down.

- [ ] **Step 4: Fix one shared no-candidate cluster at a time**

Do not touch all blocked statements together. Work cluster-by-cluster, e.g.:
- static include no-candidate
- foreach/include no-candidate
- dynamic filter no-candidate

- [ ] **Step 5: Re-run all four batches and check if the top blocker count drops**

Run the fresh batch refresh plus generalization summary again.

Expected: `NO_PATCHABLE_CANDIDATE_SELECTED` raw count decreases, or is reclassified more accurately.

Task 3 fresh rerun ids recorded on 2026-04-08:
- `generalization-batch1`: `run_7029993ee1c5`
- `generalization-batch2`: `run_cb3fbc83bf80`
- `generalization-batch3`: `run_cac46f3346ed`
- `generalization-batch4`: `run_9f2563966aac`

Task 3 outcome:
- grouped blocker focus remains `NO_PATCHABLE_CANDIDATE_SELECTED: 8`
- raw blocker breakdown is now explicit:
  - `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY: 4`
  - `NO_SAFE_BASELINE_RECOVERY: 3`
  - `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY: 1`


### Task 4: Attack Shared Blocker Program B — `SEMANTIC_GATE_NOT_PASS` and `VALIDATE_STATUS_NOT_PASS`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] **Step 1: Build a failing regression set from the current semantic blockers**

Focus only on the currently blocked generalization statements that land in:
- `SEMANTIC_GATE_NOT_PASS`
- `VALIDATE_STATUS_NOT_PASS`

- [ ] **Step 2: Split true semantic risk from comparison weakness**

For each statement, decide whether the blocker is:
- correct and should remain blocked
- or caused by a comparison weakness such as wrapper identity, fragment rendering drift, or degraded row-count comparison

- [ ] **Step 3: Fix only proven comparison weaknesses**

Examples of acceptable fixes:
- canonical wrapper equivalence
- whitespace-only replay drift
- projection-safe baseline override with evidence

Examples that are out of scope:
- making risky EXISTS/JOIN rewrites automatically safe
- lowering semantic requirements just to increase pass rate

- [ ] **Step 4: Keep blocked boundaries explicit**

If a statement still should not patch, leave it blocked but make the blocker reason stable and defensible.

- [ ] **Step 5: Re-run all four batches and compare semantic blocker counts**

Expected: either fewer semantic blockers, or a cleaner separation where remaining semantic blockers are clearly intended boundaries.

Task 4 fresh rerun ids recorded on 2026-04-08:
- `generalization-batch1`: `run_d92d991c5c3e`
- `generalization-batch2`: `run_3b6164a71911`
- `generalization-batch3`: `run_9a7906cd31bd`
- `generalization-batch4`: `run_b383ae2b8c08`

Task 4 outcome:
- grouped semantic blocker count dropped to `0`
- grouped validate blocker count dropped to `2`
- raw blockers are now explicit:
  - `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION: 1`
  - `VALIDATE_SEMANTIC_ERROR: 1`


### Task 5: Convert `SHAPE_FAMILY_NOT_TARGET` Into a Deliberate Boundary Program

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/convergence_registry.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-08-generalization-program-view.md`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Enumerate current not-target statements from the fresh baseline**

Use the batch summary output, not code inspection, to list statements currently blocked by `SHAPE_FAMILY_NOT_TARGET`.

- [ ] **Step 2: Split them into two buckets**

For each not-target statement, decide:
- `keep_blocked`: current product boundary is correct
- `promote_next`: close enough to an existing supported family that it should be targeted in the next batch

- [ ] **Step 3: Add a tiny registry or comment map for deliberate boundaries**

Do not leave “not target” as accidental. Add a small data-driven place to explain deliberate blocked families or patterns.

- [ ] **Step 4: Do not widen broad families accidentally**

Explicitly protect:
- broad join statements
- plain foreach/include predicates
- ambiguous fragment chains

from being promoted by loose keyword detection.

- [ ] **Step 5: Produce the candidate pool for `generalization-batch5`**

The output of this task is a curated list of 5 statements, chosen from the `promote_next` bucket.


### Task 6: Close the Program Loop and Set the Next Stage Gate

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch5.md`
- Verify only: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/projects/sample_project/runs/`

- [ ] **Step 1: Refresh all four batches one final time**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 480
```

- [ ] **Step 2: Produce the final four-batch summary**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=<run_dir> \
  --batch-run generalization-batch2=<run_dir> \
  --batch-run generalization-batch3=<run_dir> \
  --batch-run generalization-batch4=<run_dir> \
  --format text
```

- [ ] **Step 3: Check exit criteria for moving forward**

The program is considered complete when:
- all four batch run ids are fresh and reproducible
- the summary gives one clear top blocker focus
- blocked reasons are stable across reruns
- no previously ready statement regresses

- [ ] **Step 4: Write the next batch plan**

Only after the summary stabilizes, write `generalization-batch5` as a focused plan against the chosen next blocker or promote-next pool.

- [ ] **Step 5: Run full regression**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS with no regression in previously completed family or generalization work.

Task 5 outcome recorded on 2026-04-08:
- `keep_blocked`
  - `demo.order.harness.findOrdersByNos` -> `PLAIN_FOREACH_INCLUDE_PREDICATE`
  - `demo.shipment.harness.findShipmentsByOrderIds` -> `PLAIN_FOREACH_INCLUDE_PREDICATE`
  - `demo.test.complex.multiFragmentSeparate` -> `AMBIGUOUS_FRAGMENT_CHAIN`
- `promote_next`
  - `demo.user.advanced.findUsersByKeyword` -> `CHOOSE_GUARDED_FILTER_EXTENSION`

Task 5 candidate pool for `generalization-batch5`:
- `demo.user.advanced.findUsersByKeyword`
- `demo.test.complex.chooseBasic`

Task 6 fresh rerun ids recorded on 2026-04-08:
- `generalization-batch1`: `run_03c5d0f2aac3`
- `generalization-batch2`: `run_238cdb7eac70`
- `generalization-batch3`: `run_6471b0ca1e40`
- `generalization-batch4`: `run_8469f645eda4`

Task 6 outcome:
- four fresh batch baselines are reproducible again after fixing the `fromClauseSubquery` and `wrapperCount` convergence regressions
- no previously ready statement regressed in the final fresh rerun
- current overall focus remains `NO_PATCHABLE_CANDIDATE_SELECTED`
- next stage is tracked in `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch5-program.md`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
