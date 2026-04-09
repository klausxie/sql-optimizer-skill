# Generalization Batch 7 Intake Plan

> **Context:** This intake starts after the shared candidate-selection program completed with a fresh `batch1..6` rerun on 2026-04-08:
> - `generalization-batch1`: `run_a90d09a35501`
> - `generalization-batch2`: `run_63fa40d43788`
> - `generalization-batch3`: `run_7a429ab21b78`
> - `generalization-batch4`: `run_9e0f22aab6fa`
> - `generalization-batch5`: `run_8f8c911555db`
> - `generalization-batch6`: `run_a0515c9ae14e`
>
> Fresh decision view:
> - `total_statements = 30`
> - `AUTO_PATCHABLE = 9`
> - `MANUAL_REVIEW = 21`
> - `ready_regressions = 0`
> - `blocked_boundary_regressions = 0`
> - `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`

**Goal:** Open `generalization-batch7` as a focused intake for the remaining shared candidate-selection gap, without widening the deliberate blocked boundaries from `batch4` and the semantic-risk tails already exposed in `batch3` and `batch5`.

**Architecture:** Keep the current run/artifact model, convergence contracts, and blocked-boundary registry unchanged. Batch7 should focus on statements that are already in-scope or near in-scope, but still collapse into `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` or closely related candidate-selection blockers. Do not use this intake to broaden `FOREACH/INCLUDE` predicate boundaries, fragment-chain support, or unsafe semantic rewrites.

## Intake Candidate Pool

These five statements form the `generalization-batch7` candidate pool:

1. `demo.order.harness.listOrdersWithUsersPaged`
2. `demo.shipment.harness.findShipments`
3. `demo.test.complex.chooseBasic`
4. `demo.test.complex.chooseMultipleWhen`
5. `demo.user.advanced.findUsersByKeyword`

## Why these five

- They remain in the dominant shared blocker cluster: `NO_PATCHABLE_CANDIDATE_SELECTED`, especially `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`.
- They are not deliberate blocked-boundary statements.
- They are better next candidates than the current semantic-risk tails:
  - `demo.test.complex.existsSubquery`
  - `demo.test.complex.leftJoinWithNull`
  - `demo.test.complex.chooseWithLimit`
  - `demo.test.complex.selectWithFragmentChoose`
- They let the next program keep focusing on shared candidate selection instead of opening a new family or widening true semantic-risk support.

## Explicit Non-Goals

Batch7 must keep these statements out of scope:

- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.chooseWithLimit`

Those remain blocked either because they are explicit boundaries or because their current blocker is a true semantic/unsupported-strategy tail rather than a shared candidate-selection gap.

## Recommended Program Focus

Start with the two cross-batch repeated statements:

- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`

Then move to the choose-path low-value statements:

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.user.advanced.findUsersByKeyword`

The next program should prefer:

- more precise candidate pruning
- safe baseline recovery only when it is already structurally justified
- keeping semantic-risk tails blocked

over opening any new patch family or relaxing semantic gates.
