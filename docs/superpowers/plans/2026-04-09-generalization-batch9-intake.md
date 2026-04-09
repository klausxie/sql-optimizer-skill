# Generalization Batch9 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize widening blocked semantic-risk or unsupported-strategy families.

**Goal:** Open the next generalization batch around the still-dominant truthful blocker after `batch8` fresh replay:

1. `NO_SAFE_BASELINE_RECOVERY`

This intake keeps one semantic canary inside scope so the safe-baseline work does not accidentally blur a real semantic blocker.

This intake explicitly avoids reopening:
- broad choose support
- plain `FOREACH/INCLUDE` predicate support
- fragment-chain / fragment-choose support
- join/exists semantic relaxations
- offset-to-keyset promotion
- `IN`-subquery unsupported strategies as if they were safe-baseline candidates

## Fresh Program Baseline

Fresh replay run:

- `batch8`: `run_a1436100774b`

Current `batch8` summary:

- `total_statements = 5`
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Per-statement truth:

- `demo.user.advanced.findUsersByKeyword` -> `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.order.harness.findOrdersByUserIdsAndStatus` -> `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

Important excluded truth:

- `demo.test.complex.inSubquery` is no longer a semantic target. It is now a clean `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY` canary after the wording-drift fix in `batch8`.

## Batch9 Target Set

`batch9` should be the next five-statement blocker program:

1. `demo.user.advanced.findUsersByKeyword`
2. `demo.shipment.harness.findShipments`
3. `demo.test.complex.multiFragmentLevel1`
4. `demo.order.harness.findOrdersByUserIdsAndStatus`
5. `demo.order.harness.listOrdersWithUsersPaged`

Why these five:

- The first four are the current truthful no-safe-baseline set across dynamic filter and static include shapes.
- `findOrdersByUserIdsAndStatus` keeps the safe-baseline lane honest by forcing the system to distinguish a generic no-safe-baseline gap from a `FOREACH + INCLUDE + IF` predicate shape that still has no supported baseline family.
- `listOrdersWithUsersPaged` stays in scope only as a semantic canary. It must not be “fixed” by weakening semantic comparison while safe-baseline work is in progress.

## Non-Goals

These stay out of scope and must not become collateral promotions:

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.inSubquery`

## Success Standard

`batch9` is successful if it does one of the following safely:

- keeps the four safe-baseline targets blocked, but with cleaner and more stable reasons
- promotes one or more of those four only through already-supported safe paths
- proves that one of the four was mis-bucketed and moves it to a more honest blocker
- keeps `listOrdersWithUsersPaged` blocked for the same semantic class of reason

`batch9` is not successful if it:

- introduces a new patch family
- relaxes semantic gates for convenience
- weakens the `listOrdersWithUsersPaged` semantic blocker
- reclassifies unsupported-strategy canaries into safe-baseline work
- weakens any listed non-goal boundary
