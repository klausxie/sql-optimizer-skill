# Generalization Batch 6 Intake Plan

> **Context:** This plan starts after the fresh five-batch rerun completed on 2026-04-08 with:
> - `generalization-batch1`: `run_fa51ed4fbc1d`
> - `generalization-batch2`: `run_f59fd5b2d430`
> - `generalization-batch3`: `run_7fe9ba6426a7`
> - `generalization-batch4`: `run_d356e79f227d`
> - `generalization-batch5`: `run_a51c5bd7c65b`
>
> Overall decision view:
> - `AUTO_PATCHABLE = 3`
> - `MANUAL_REVIEW = 22`
> - `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`
> - dominant raw reasons:
>   - `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
>   - `NO_SAFE_BASELINE_RECOVERY`
>   - a smaller `VALIDATE_SEMANTIC_ERROR / SEMANTIC_PREDICATE_CHANGED` tail

**Goal:** Open a dedicated `generalization-batch6` program that attacks the shared candidate-selection gap exposed by batches `1..5`, without widening the deliberately blocked `SHAPE_FAMILY_NOT_TARGET` boundaries from batch4 and batch5.

**Architecture:** Keep the current run/artifact flow, convergence summaries, and blocked-boundary registry unchanged. Batch6 should focus on a narrow cross-batch cluster where the system already recognizes the statements as in-scope but still fails to materialize a safe baseline candidate, typically ending in `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` or `NO_SAFE_BASELINE_RECOVERY`. The work should improve candidate selection/recovery first, then rerun the whole generalization program to confirm no ready regressions.

**Tech Stack:** Python, pytest, `scripts/run_sample_project.py`, `scripts/ci/generalization_refresh.py`, `scripts/ci/generalization_summary.py`, `sample_project` fixture mappers, candidate-generation support/engine, convergence/validate layers.

## Intake Candidate Pool

These five statements form the initial `generalization-batch6` candidate pool:

1. `demo.order.harness.listOrdersWithUsersPaged`
2. `demo.shipment.harness.findShipments`
3. `demo.test.complex.staticSimpleSelect`
4. `demo.test.complex.inSubquery`
5. `demo.test.complex.includeSimple`

### Why these five

- They are already inside supported families or near-supported families.
- They currently fail for candidate-selection reasons rather than explicit out-of-scope boundaries.
- They cover the two dominant sub-clusters:
  - `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
  - `NO_SAFE_BASELINE_RECOVERY`
- They do not require widening the guarded `FOREACH/INCLUDE`, ambiguous fragment chain, or fragment-choose boundaries.

### Explicit Non-Goals

Batch6 must keep these statements blocked and out of scope:

- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.selectWithFragmentChoose`

Those remain deliberate blocked boundaries, not candidate-selection misses.

## Proposed Execution Tasks

### Task 1: Promote `generalization-batch6` to a runnable scope

- Add `generalization-batch6` to the shared scope registry.
- Wire it through `run_sample_project.py` and `generalization_refresh.py`.
- Add script tests proving the new batch is runnable and refreshable.

### Task 2: Lock the batch6 regression set

- Add targeted regression tests for the five statements above.
- Prove their current blocker class is candidate-selection related, not `SHAPE_FAMILY_NOT_TARGET`.
- Add guard tests that the known blocked-boundary statements listed above stay blocked.

### Task 3: Improve shared candidate recovery, not family breadth

Only fix the candidate-selection gap shared across these statements:

- promote safe baseline recovery when the original SQL already matches a known low-risk simplification
- keep speculative rewrites pruned
- do not widen template rewrite scope
- do not add support for new blocked families as part of this work

This task should prefer:

- safer recovery
- cleaner low-value classification
- more precise no-candidate reasons

over aggressive new rewrite families.

### Task 4: Re-run `generalization-batch6` and classify outcomes

Expected stable end state:

- some statements may become `AUTO_PATCHABLE`
- the rest must end in precise candidate-selection blockers
- none should regress into accidental `SHAPE_FAMILY_NOT_TARGET`

### Task 5: Revalidate the whole generalization program (`batch1..6`)

- run a fresh `generalization_refresh`
- summarize all six batches together
- confirm:
  - no ready regressions in earlier batches
  - blocked-boundary statements remain blocked
  - the global `decision_focus` either improves or remains clearly concentrated

## Success Criteria

Batch6 is considered successful only if all of the following are true:

1. `generalization-batch6` is runnable from the shared registry and CI-covered.
2. Earlier ready statements from batches `1..5` do not regress.
3. At least one of the five batch6 candidates either:
   - becomes `AUTO_PATCHABLE`, or
   - moves from a vague blocker into a precise candidate-selection blocker.
4. The blocked-boundary statements listed above remain blocked for the same reason class.
5. The whole-program summary still has one clear `decision_focus` after the rerun.

## Recommended First Focus

Start with the `NO_SAFE_BASELINE_RECOVERY` pair:

- `demo.test.complex.staticSimpleSelect`
- `demo.test.complex.includeSimple`

These are the most likely to improve without opening new semantic risk. After that, move to the `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` statements in the same batch.
