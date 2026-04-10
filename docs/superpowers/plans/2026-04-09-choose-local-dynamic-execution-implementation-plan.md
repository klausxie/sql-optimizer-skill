# Choose-Local Dynamic Execution Implementation Plan

> Status: substrate completed; promotion attempt closed. The remaining blocker is provider candidate quality, not missing local execution mechanics. This plan is now historical context, not the recommended next action.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real local-surface dynamic execution path for `CHOOSE_BRANCH_BODY`, including materialization, replay, patch-family binding, and patch build, without widening to statement-level fallback.

**Architecture:** Build a narrow choose-local execution substrate on top of the review-only foundation already in place. The implementation must introduce a real `replace_choose_branch_body` materialization/replay/build path and prove it on `demo.user.advanced.findUsersByKeyword`; `COLLECTION_PREDICATE_BODY` remains explicitly deferred and must stay review-only.

**Tech Stack:** Python dataclasses, ElementTree XML manipulation, existing `template_materializer` / `patch_replay` / `patching_templates` pipeline, `pytest`, sample-project replay harness.

## Closure Note

This plan succeeded at the infrastructure level:

- local choose surface location exists
- local choose materialization exists
- local choose patch build exists
- local choose replay exists

It did not succeed at the promotion level.

After the substrate was completed, a stricter choose-local optimize contract was added and replay cassettes were reseeded. The primary sentinel still remained:

- `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

That means the next missing piece is outside this implementation plan. It is a separate provider-quality investment.

---

## File Structure

### Existing files to modify

- Modify: `python/sqlopt/platforms/sql/materialization_constants.py`
  - Add choose-local materialization mode constants.
- Modify: `python/sqlopt/platforms/sql/template_materializer.py`
  - Add choose-local materialization path and choose-local replay-contract emission.
- Modify: `python/sqlopt/platforms/sql/patch_strategy_registry.py`
  - Add a narrow strategy that can emit choose-local materialization when capability conditions are met.
- Modify: `python/sqlopt/platforms/sql/patch_strategy_planner.py`
  - Keep review-only preview for deferred lanes, but allow the choose-local promoted path to surface the real local materialization.
- Modify: `python/sqlopt/platforms/sql/patch_utils.py`
  - Surface the promoted dynamic family cleanly without collapsing back to generic statement template families.
- Modify: `python/sqlopt/verification/patch_replay.py`
  - Add surface-local replay validation for choose-local patch targets.
- Modify: `python/sqlopt/stages/patching_templates.py`
  - Add choose-local patch application path; keep collection local op unsupported.
- Modify: `python/sqlopt/stages/patch_decision/gate_dynamic.py`
  - Allow only the narrow choose-local promoted lane through; keep other review-only lanes blocked.
- Modify: `python/sqlopt/patch_families/models.py`
  - Extend patch-family contract usage if needed for new local op / materialization mode.

### New files to create

- Create: `python/sqlopt/platforms/sql/dynamic_surface_locator.py`
  - Surface-local XML/template locator helpers for top-level `<where><choose>` branch targeting.
- Create: `python/sqlopt/patch_families/specs/dynamic_choose_branch_local_cleanup.py`
  - Formal patch family spec for the new narrow choose-local family.

### Tests to modify / add

- Modify: `tests/unit/sql/test_template_materialization.py`
- Modify: `tests/unit/patch/test_patch_selection.py`
- Modify: `tests/unit/patch/test_patching_templates.py`
- Modify: `tests/unit/patch/test_patch_replay.py`
- Modify: `tests/unit/patch/test_patch_generate_orchestration.py`
- Modify: `tests/unit/verification/test_validate_convergence.py`
- Modify: `tests/ci/test_generalization_summary_script.py`

### Docs to modify / create

- Modify: `docs/superpowers/plans/2026-04-09-surface-specific-dynamic-capability-program.md`
- Modify: `docs/superpowers/plans/2026-04-09-surface-specific-dynamic-capability-review.md`
- Create: `docs/superpowers/plans/2026-04-09-choose-local-dynamic-execution-review.md`

## Scope Rules

- `CHOOSE_BRANCH_BODY` is the only promotable lane in this plan.
- `COLLECTION_PREDICATE_BODY` remains review-only and deferred.
- No statement-level or fragment-level fallback may be used to implement choose-local support.
- Guardrails must remain blocked:
  - `demo.test.complex.chooseBasic`
  - `demo.test.complex.chooseMultipleWhen`
  - `demo.test.complex.chooseWithLimit`
  - `demo.test.complex.selectWithFragmentChoose`
  - `demo.shipment.harness.findShipmentsByOrderIds`
  - `demo.test.complex.multiFragmentLevel1`
  - `demo.shipment.harness.findShipments`
  - `demo.order.harness.listOrdersWithUsersPaged`
  - `demo.test.complex.includeNested`
  - `demo.user.findUsers`

## Task 1: Add Choose-Local Materialization Constants And Failing Tests

**Files:**
- Modify: `python/sqlopt/platforms/sql/materialization_constants.py`
- Test: `tests/unit/sql/test_template_materialization.py`
- Test: `tests/unit/patch/test_patching_templates.py`

- [ ] **Step 1: Write the failing materialization-mode tests**

Add tests asserting:
- `template_materializer` can return `DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE` for one narrow top-level `<where><choose>` case.
- `patching_templates` no longer rejects `replace_choose_branch_body` once the local builder exists.

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m pytest -q tests/unit/sql/test_template_materialization.py -k choose_branch
python3 -m pytest -q tests/unit/patch/test_patching_templates.py -k choose_branch_body
```

Expected:
- FAIL because the new materialization mode and choose-local patch builder do not exist yet.

- [ ] **Step 3: Add the new constants**

Add constants for:
- `DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE`
- any helper tuples or allowlists needed to thread the new mode

- [ ] **Step 4: Re-run the targeted tests**

Run the same commands.

Expected:
- tests still fail, but now on missing behavior instead of missing constants.

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/platforms/sql/materialization_constants.py tests/unit/sql/test_template_materialization.py tests/unit/patch/test_patching_templates.py
git commit -m "test: lock choose local materialization mode"
```

## Task 2: Add Choose Surface Locator And Real Materialization

**Files:**
- Create: `python/sqlopt/platforms/sql/dynamic_surface_locator.py`
- Modify: `python/sqlopt/platforms/sql/template_materializer.py`
- Test: `tests/unit/sql/test_template_materialization.py`

- [ ] **Step 1: Write failing locator/materialization tests**

Add tests for:
- locating the single top-level `<choose>` inside `<where>`
- extracting a stable target anchor for one branch
- building a choose-local materialization result with:
  - `mode = DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE`
  - `targetSurface = CHOOSE_BRANCH_BODY`
  - `replace_choose_branch_body`

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m pytest -q tests/unit/sql/test_template_materialization.py -k 'choose_local or choose_branch'
```

Expected:
- FAIL because the locator/materializer cannot yet build local choose edits.

- [ ] **Step 3: Implement the locator helper**

Implement focused helpers in `dynamic_surface_locator.py` for:
- identifying one top-level `<where><choose>`
- selecting a specific immediate `<when>` / `<otherwise>` branch
- extracting branch-local inner template
- generating structured `targetAnchor`

- [ ] **Step 4: Implement narrow choose-local materialization**

In `template_materializer.py`, add a choose-local path that:
- only activates for the primary sentinel shape
- emits `replace_choose_branch_body`
- stores surface-local `beforeTemplate` / `afterTemplate`
- never falls back to `replace_statement_body`

- [ ] **Step 5: Re-run the tests**

Run:
```bash
python3 -m pytest -q tests/unit/sql/test_template_materialization.py -k 'choose_local or choose_branch'
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/dynamic_surface_locator.py python/sqlopt/platforms/sql/template_materializer.py tests/unit/sql/test_template_materialization.py
git commit -m "feat: add choose local template materialization"
```

## Task 3: Add Surface-Local Replay Execution

**Files:**
- Modify: `python/sqlopt/verification/patch_replay.py`
- Modify: `python/sqlopt/platforms/sql/template_materializer.py`
- Test: `tests/unit/patch/test_patch_replay.py`

- [ ] **Step 1: Write failing replay tests**

Add tests asserting choose-local replay:
- accepts a matching choose-branch-local edit
- rejects sibling branch drift
- rejects envelope drift
- rejects branch-identity ambiguity

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patch_replay.py -k choose_branch
```

Expected:
- FAIL because replay only understands statement/fragment modes today.

- [ ] **Step 3: Implement choose-local replay checks**

Extend `patch_replay.py` so replay can validate:
- `targetSurface = CHOOSE_BRANCH_BODY`
- `targetAnchor`
- sibling branch structure
- `<where>` envelope preservation

- [ ] **Step 4: Ensure replay refuses fallback**

Explicitly fail replay if:
- statement-level comparison is the only proof path
- fragment-level comparison is the only proof path

- [ ] **Step 5: Re-run the tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patch_replay.py -k choose_branch
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/verification/patch_replay.py python/sqlopt/platforms/sql/template_materializer.py tests/unit/patch/test_patch_replay.py
git commit -m "feat: add choose local replay verification"
```

## Task 4: Add Narrow Choose Patch Family And Patch Build Path

**Files:**
- Create: `python/sqlopt/patch_families/specs/dynamic_choose_branch_local_cleanup.py`
- Modify: `python/sqlopt/platforms/sql/patch_utils.py`
- Modify: `python/sqlopt/stages/patching_templates.py`
- Modify: `python/sqlopt/stages/patch_decision/gate_dynamic.py`
- Test: `tests/unit/patch/test_patching_templates.py`
- Test: `tests/unit/patch/test_patch_generate_orchestration.py`

- [ ] **Step 1: Write failing family/build tests**

Add tests asserting:
- the new choose-local family is selected for the primary sentinel only
- `patching_templates` can apply `replace_choose_branch_body`
- collection local op remains unsupported
- guardrail choose statements still do not generate patches

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patching_templates.py -k choose_branch_body
python3 -m pytest -q tests/unit/patch/test_patch_generate_orchestration.py -k choose_branch_body
```

Expected:
- FAIL because the family and builder do not exist yet.

- [ ] **Step 3: Add the family spec**

Create `dynamic_choose_branch_local_cleanup.py` with:
- narrow dynamic scope
- required materialization mode `DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE`
- required template op `replace_choose_branch_body`

- [ ] **Step 4: Implement choose-local patch build**

In `patching_templates.py`, add a local-surface patch path that:
- resolves the owning XML statement
- rewrites only the target branch body
- preserves the rest of the `<choose>` and `<where>`

- [ ] **Step 5: Gate the lane narrowly**

In `gate_dynamic.py`, allow only the promoted choose-local family through.
All other choose/collection review-only lanes must still short-circuit to manual review.

- [ ] **Step 6: Re-run the tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patching_templates.py -k choose_branch_body
python3 -m pytest -q tests/unit/patch/test_patch_generate_orchestration.py -k choose_branch_body
```

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add python/sqlopt/patch_families/specs/dynamic_choose_branch_local_cleanup.py python/sqlopt/platforms/sql/patch_utils.py python/sqlopt/stages/patching_templates.py python/sqlopt/stages/patch_decision/gate_dynamic.py tests/unit/patch/test_patching_templates.py tests/unit/patch/test_patch_generate_orchestration.py
git commit -m "feat: add choose local patch family and builder"
```

## Task 5: Integrate Strategy Selection And Validate Sentinel Promotion

**Files:**
- Modify: `python/sqlopt/platforms/sql/patch_strategy_registry.py`
- Modify: `python/sqlopt/platforms/sql/patch_strategy_planner.py`
- Modify: `python/sqlopt/stages/validate_convergence.py`
- Test: `tests/unit/patch/test_patch_selection.py`
- Test: `tests/unit/verification/test_validate_convergence.py`

- [ ] **Step 1: Write failing integration tests**

Add tests asserting:
- `findUsersByKeyword` gets the choose-local strategy and family
- convergence can classify the promoted lane as `AUTO_PATCHABLE`
- non-goal choose guardrails remain blocked

- [ ] **Step 2: Run the failing tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patch_selection.py -k choose
python3 -m pytest -q tests/unit/verification/test_validate_convergence.py -k choose
```

Expected:
- FAIL because selection/convergence do not yet recognize the promoted family.

- [ ] **Step 3: Implement the narrow choose strategy**

Add a strategy in `patch_strategy_registry.py` that:
- only activates on the primary choose-local sentinel shape
- requires exact replay evidence
- emits the new materialization mode and op

- [ ] **Step 4: Wire family selection and convergence**

Update planner / family derivation / convergence so the primary sentinel can surface as:
- a distinct choose-local family
- `AUTO_PATCHABLE` only when all choose-local conditions are met

- [ ] **Step 5: Re-run the tests**

Run:
```bash
python3 -m pytest -q tests/unit/patch/test_patch_selection.py -k choose
python3 -m pytest -q tests/unit/verification/test_validate_convergence.py -k choose
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/patch_strategy_registry.py python/sqlopt/platforms/sql/patch_strategy_planner.py python/sqlopt/stages/validate_convergence.py tests/unit/patch/test_patch_selection.py tests/unit/verification/test_validate_convergence.py
git commit -m "feat: promote narrow choose local capability"
```

## Task 6: Fresh Replay Review And Final Verdict

**Files:**
- Modify: `docs/superpowers/plans/2026-04-09-surface-specific-dynamic-capability-review.md`
- Create: `docs/superpowers/plans/2026-04-09-choose-local-dynamic-execution-review.md`
- Test: `tests/ci/test_generalization_summary_script.py`

- [ ] **Step 1: Add / update summary tests**

Add assertions for fresh replay expectations:
- `findUsersByKeyword` may become `AUTO_PATCHABLE`
- all choose guardrails remain blocked
- collection remains review-only

- [ ] **Step 2: Run the summary test red/green cycle**

Run:
```bash
python3 -m pytest -q tests/ci/test_generalization_summary_script.py -k 'batch9 or batch13 or choose'
```

- [ ] **Step 3: Refresh the relevant replay batches**

Run:
```bash
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --max-seconds 240
python3 scripts/ci/generalization_refresh.py --batch generalization-batch13 --max-seconds 240
```

Expected:
- no ready regressions
- no blocked-boundary regressions

- [ ] **Step 4: Inspect summary output**

Run:
```bash
python3 scripts/ci/generalization_summary.py --batch-run generalization-batch9=<new-run> --format text
python3 scripts/ci/generalization_summary.py --batch-run generalization-batch13=<new-run> --format text
```

- [ ] **Step 5: Write the final review**

Capture one of two outcomes:
- success: narrow choose lane promoted safely
- no-go: substrate still insufficient, keep choose deferred

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-09-surface-specific-dynamic-capability-review.md docs/superpowers/plans/2026-04-09-choose-local-dynamic-execution-review.md tests/ci/test_generalization_summary_script.py
git commit -m "docs: review choose local dynamic execution"
```

## Final Verification

- [ ] **Step 1: Run the focused unit/integration suite**

```bash
python3 -m pytest -q \
  tests/unit/sql/test_template_materialization.py \
  tests/unit/patch/test_patch_selection.py \
  tests/unit/patch/test_patching_templates.py \
  tests/unit/patch/test_patch_replay.py \
  tests/unit/patch/test_patch_generate_orchestration.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/ci/test_generalization_summary_script.py
```

Expected:
- all targeted tests pass

- [ ] **Step 2: Run fresh replay checks**

```bash
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --max-seconds 240
python3 scripts/ci/generalization_refresh.py --batch generalization-batch13 --max-seconds 240
```

- [ ] **Step 3: Record the verdict**

Document whether:
- `CHOOSE_BRANCH_BODY` became a real supported narrow lane
- or the product still lacks enough substrate and must keep it deferred

- [ ] **Step 4: Stop**

Do **not** reopen collection in this same plan unless the choose lane is cleanly successful.
