# Shared Candidate-Selection Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the shared `NO_PATCHABLE_CANDIDATE_SELECTED` blocker cluster across `generalization-batch1..6` without widening the deliberately blocked `SHAPE_FAMILY_NOT_TARGET` families.

**Architecture:** Keep the current run/artifact model, convergence contracts, and blocked-boundary registry intact. Treat the current system state as a blocker-driven program: first freeze the fresh `batch1..6` baseline, then attack the two dominant shared blocker families (`NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` and `NO_SAFE_BASELINE_RECOVERY`), then rerun all six batches and decide whether the system is ready to open `batch7`. This plan explicitly avoids adding new patch families or broadening `FOREACH`, ambiguous fragment chain, or fragment-choose support.

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_refresh.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture mappers, candidate-generation engine/support/rules, semantic equivalence, validate convergence, harness fixture scenarios.

---

## Current Baseline

Fresh program baseline as of 2026-04-08:

- `generalization-batch1`: `run_b7d5117396af`
- `generalization-batch2`: `run_082e49d30889`
- `generalization-batch3`: `run_2a147a539278`
- `generalization-batch4`: `run_984f1fdc1212`
- `generalization-batch5`: `run_1d4b55666057`
- `generalization-batch6`: `run_ec6e24bf1419`

Current decision view:

- `total_statements = 30`
- `AUTO_PATCHABLE = 3`
- `MANUAL_REVIEW = 27`
- `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`

Dominant raw blockers:

- `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY = 14`
- `SHAPE_FAMILY_NOT_TARGET = 4`
- `NO_SAFE_BASELINE_RECOVERY = 3`
- `VALIDATE_SEMANTIC_ERROR = 3`

Ready statements that must not regress:

- `demo.test.complex.fromClauseSubquery`
- `demo.user.countUser`
- `demo.test.complex.wrapperCount`

Explicit blocked boundaries that must stay blocked:

- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.selectWithFragmentChoose`

---

### Task 1: Freeze the Shared Blocker Inventory and Comparison View

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`

- [ ] **Step 1: Create a single blocker inventory module**

Create `python/sqlopt/devtools/generalization_blocker_inventory.py` to hold the canonical program metadata:

```python
READY_SENTINEL_SQL_KEYS = [
    "demo.test.complex.fromClauseSubquery",
    "demo.user.countUser",
    "demo.test.complex.wrapperCount",
]

BLOCKED_BOUNDARY_SQL_KEYS = [
    "demo.order.harness.findOrdersByNos",
    "demo.shipment.harness.findShipmentsByOrderIds",
    "demo.test.complex.multiFragmentSeparate",
    "demo.test.complex.selectWithFragmentChoose",
]
```

- [ ] **Step 2: Add cluster definitions for the current blocker program**

Extend the same module with exact SQL keys for:
- `LOW_VALUE_ONLY_CLUSTER`
- `NO_SAFE_BASELINE_RECOVERY_CLUSTER`
- `SEMANTIC_ERROR_CLUSTER`
- `UNSUPPORTED_STRATEGY_CLUSTER`

Only include statements from the fresh `batch1..6` baseline.

- [ ] **Step 3: Extend `generalization_summary.py` with comparison-aware output**

Add a stable conclusion block that prints:

```text
ready_regressions=0
blocked_boundary_regressions=0
decision_focus=NO_PATCHABLE_CANDIDATE_SELECTED
recommended_next_step=fix_shared_candidate_selection_gaps
```

The script must stay purely observational.

- [ ] **Step 4: Add a refresh smoke test for the six-batch program**

Run:

```bash
python3 -m pytest -q tests/ci/test_generalization_refresh_script.py tests/ci/test_generalization_summary_script.py
```

Expected: PASS with the new inventory and output shape covered.

- [ ] **Step 5: Record the baseline inside the plan notes**

Keep the six fresh run ids above in this plan and in the summary command examples so later work does not depend on deleted or ad-hoc run directories.

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/devtools/generalization_blocker_inventory.py scripts/ci/generalization_summary.py scripts/ci/generalization_refresh.py tests/ci/test_generalization_summary_script.py tests/ci/test_generalization_refresh_script.py docs/superpowers/plans/2026-04-08-shared-candidate-selection-program.md
git commit -m "chore: freeze shared generalization blocker inventory"
```


### Task 2: Program A — Reduce `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_rules/low_value_speculative.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] **Step 1: Write the failing regression set for the current low-value cluster**

Add exact tests for statements currently blocked by `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`, including at minimum:

- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.inSubquery`
- `demo.test.complex.multiFragmentLevel1`
- `demo.test.complex.staticOrderBy`
- `demo.user.advanced.findUsersByKeyword`

The tests must assert whether each statement should:
- remain low-value blocked
- or surface a safe baseline recovery

- [ ] **Step 2: Centralize wording-drift handling**

Move repetitive strategy-wording matching out of the ad-hoc checks and into one helper path:

```python
def is_low_value_semantic_rewrite(strategy: str) -> bool:
    ...
```

This helper should cover the actual wording variants already observed in real runs, not speculative future phrases.

- [ ] **Step 3: Distinguish “unsafe candidate was correctly pruned” from “candidate family is unsupported”**

`candidate_generation_diagnostics` should preserve:

- `LOW_VALUE_PRUNED_TO_EMPTY`
- `NO_SAFE_BASELINE_SHAPE_MATCH`
- unsupported-strategy cases

Do not collapse these into one bucket.

- [ ] **Step 4: Only open safe baseline recovery when the original SQL already matches a known low-risk simplification**

Examples:
- safe static wrapper collapse
- safe count wrapper collapse
- safe distinct/order/limit cleanup

Do not use this task to introduce new template patch families.

- [ ] **Step 5: Re-run the affected statements first**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch6 --max-steps 0 --max-seconds 240
python3 scripts/ci/generalization_summary.py --batch-run generalization-batch6=tests/fixtures/projects/sample_project/runs/run_ec6e24bf1419 --format text
```

Expected:
- no statement regresses into `SHAPE_FAMILY_NOT_TARGET`
- low-value blockers become more precise or fewer

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/candidate_generation_engine.py python/sqlopt/platforms/sql/candidate_generation_support.py python/sqlopt/platforms/sql/candidate_generation_rules/low_value_speculative.py tests/unit/sql/test_candidate_generation_engine.py tests/unit/sql/test_candidate_generation_support.py tests/unit/verification/test_verification_stage_integration.py
git commit -m "feat: reduce shared low-value candidate blockers"
```


### Task 3: Program B — Reduce `NO_SAFE_BASELINE_RECOVERY`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_rules/recovery_safe_baseline.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/rewrite_facts.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_rewrite_facts.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Write the failing regression set for the current no-safe-baseline pair**

At minimum cover:

- `demo.test.complex.staticSimpleSelect`
- `demo.test.complex.includeSimple`

These tests must assert the current blocker exactly:

```python
assert outcome.diagnostics.recovery_reason == "NO_SAFE_BASELINE_SHAPE_MATCH"
```

- [ ] **Step 2: Map current safe-baseline families explicitly**

Do not infer from broad shape names. Add explicit recovery paths for the exact current safe families already supported elsewhere:
- static include wrapper collapse
- static statement rewrite
- safe wrapper collapse

- [ ] **Step 3: Prevent recovery from leaking into blocked boundary families**

Add tests proving that:

- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.selectWithFragmentChoose`

still have no safe baseline recovery.

- [ ] **Step 4: Re-run the two-statement focus batch**

Run:

```bash
python3 scripts/run_sample_project.py --scope generalization-batch6 --max-steps 0 --max-seconds 240
```

Expected:
- either one statement becomes `AUTO_PATCHABLE`
- or both remain blocked but with the same clean `NO_SAFE_BASELINE_RECOVERY`

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/candidate_generation_support.py python/sqlopt/platforms/sql/candidate_generation_rules/recovery_safe_baseline.py python/sqlopt/platforms/sql/rewrite_facts.py tests/unit/sql/test_candidate_generation_support.py tests/unit/sql/test_rewrite_facts.py tests/unit/verification/test_validate_convergence.py
git commit -m "feat: improve safe baseline recovery for generalization blockers"
```


### Task 4: Program C — Harden Semantic and Unsupported-Strategy Boundaries

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/convergence_registry.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] **Step 1: Write the failing boundary tests**

Cover the current semantic/unsupported-strategy tail:

- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.fragmentMultiplePlaces`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseWithLimit`

- [ ] **Step 2: Split “true semantic risk” from “comparison weakness”**

Only fix cases where the comparison is weak. Do not relax semantic rules just to convert blockers into passes.

Allowed examples:
- wrapper identity equivalence
- alias-only projection normalization

Forbidden examples:
- auto-allowing EXISTS/JOIN rewrites with changed predicates
- lowering semantic confidence thresholds globally

- [ ] **Step 3: Keep unsupported strategy tails explicit**

If a statement is blocked because its only remaining candidate is truly unsupported, the convergence result should stay explicit:

```json
{
  "conflictReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY"
}
```

- [ ] **Step 4: Run the semantic tail regression slice**

Run:

```bash
python3 -m pytest -q tests/unit/sql/test_semantic_equivalence.py tests/unit/verification/test_validate_convergence.py tests/unit/verification/test_verification_stage_integration.py
```

Expected: PASS with blocked boundaries preserved.

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/semantic_equivalence.py python/sqlopt/stages/validate_convergence.py python/sqlopt/stages/convergence_registry.py tests/unit/sql/test_semantic_equivalence.py tests/unit/verification/test_validate_convergence.py tests/unit/verification/test_verification_stage_integration.py
git commit -m "feat: harden semantic and unsupported strategy boundaries"
```


### Task 5: Re-run `generalization-batch1..6` and Compare the Whole Program

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_refresh.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`

- [ ] **Step 1: Run a fresh six-batch refresh**

Run:

```bash
python3 scripts/ci/generalization_refresh.py --max-seconds 480
```

Record the fresh baseline ids in the task notes:

- `generalization-batch1`: `run_b7d5117396af`
- `generalization-batch2`: `run_082e49d30889`
- `generalization-batch3`: `run_2a147a539278`
- `generalization-batch4`: `run_984f1fdc1212`
- `generalization-batch5`: `run_1d4b55666057`
- `generalization-batch6`: `run_ec6e24bf1419`

- [ ] **Step 2: Run the whole-program summary**

Run:

```bash
python3 scripts/ci/generalization_summary.py \
  --batch-run generalization-batch1=tests/fixtures/projects/sample_project/runs/run_b7d5117396af \
  --batch-run generalization-batch2=tests/fixtures/projects/sample_project/runs/run_082e49d30889 \
  --batch-run generalization-batch3=tests/fixtures/projects/sample_project/runs/run_2a147a539278 \
  --batch-run generalization-batch4=tests/fixtures/projects/sample_project/runs/run_984f1fdc1212 \
  --batch-run generalization-batch5=tests/fixtures/projects/sample_project/runs/run_1d4b55666057 \
  --batch-run generalization-batch6=tests/fixtures/projects/sample_project/runs/run_ec6e24bf1419 \
  --format text
```

- [ ] **Step 3: Verify the program gates**

Expected:
- `ready_regressions=0`
- blocked boundaries remain blocked
- `decision_focus` remains single and clear
- `NO_PATCHABLE_CANDIDATE_SELECTED` either drops or becomes more precise

- [ ] **Step 4: Add/adjust CI coverage only if output shape changed**

Do not expand CI scope otherwise.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/generalization_refresh.py scripts/ci/generalization_summary.py tests/ci/test_generalization_refresh_script.py tests/ci/test_generalization_summary_script.py
git commit -m "chore: refresh and compare generalization program"
```


### Task 6: Freeze the Next Intake (`batch7`) From the Updated Decision View

**Files:**
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-08-generalization-batch7-intake.md`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`

- [ ] **Step 1: Pick only statements that should be promoted**

Use the refreshed decision view to build a new five-statement intake. Do not promote:
- current blocked boundary statements
- statements still blocked by true semantic risk

- [ ] **Step 2: Encode the batch7 candidate pool in one place**

Add:

```python
GENERALIZATION_BATCH7_SQL_KEYS = [
    ...
]
```

to `sample_project_family_scopes.py`.

- [ ] **Step 3: Add the corresponding `run_sample_project.py` scope smoke coverage**

Run:

```bash
python3 -m pytest -q tests/ci/test_run_sample_project_script.py
```

Expected: PASS with `generalization-batch7` recognized.

- [ ] **Step 4: Save the intake rationale**

In the new intake plan, list:
- promoted statements
- held-back statements
- the exact blocker reason for each held-back statement

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-08-generalization-batch7-intake.md python/sqlopt/devtools/sample_project_family_scopes.py tests/ci/test_run_sample_project_script.py
git commit -m "docs: freeze generalization batch7 intake"
```


## Final Verification

- [ ] **Step 1: Run the targeted blocker program regression suites**

```bash
python3 -m pytest -q \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/sql/test_candidate_generation_support.py \
  tests/unit/sql/test_semantic_equivalence.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/unit/verification/test_verification_stage_integration.py \
  tests/ci/test_generalization_refresh_script.py \
  tests/ci/test_generalization_summary_script.py \
  tests/ci/test_run_sample_project_script.py
```

Expected: PASS.

- [ ] **Step 2: Run full regression**

```bash
python3 -m pytest -q
```

Expected: PASS with no ready regressions.

- [ ] **Step 3: Save the final six-batch summary in task notes**

Copy the final `generalization_summary.py --format text` output into the task notes or PR body so future work starts from the same program state.
