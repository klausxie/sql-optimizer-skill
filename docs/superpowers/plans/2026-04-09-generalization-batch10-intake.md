# Generalization Batch10 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize widening join/exists semantics, multi-fragment include recovery, or new patch families.

**Goal:** Open the next generalization batch around the truthful mixed lane visible after `batch9` fresh replay:

1. `NO_SAFE_BASELINE_RECOVERY`
2. `SEMANTIC_PREDICATE_CHANGED`

This intake keeps one unsupported-strategy canary inside scope so safe-baseline clarification work does not accidentally blur real blocked boundaries.

This intake explicitly avoids reopening:
- broad `JOIN` or `EXISTS` semantic relaxation
- `OFFSET -> keyset` or pagination semantics weakening
- generic multi-fragment include recovery
- new patch families for `left join`, `exists`, or `group by`
- treating unsupported strategy wording drift as safe-baseline work

## Fresh Program Baseline

Fresh replay run:

- `batch9`: `run_07d863a7b7a9`
- `batch10`: `run_7cdb98d1eb49`

Current `batch10` summary:

- `total_statements = 5`
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Per-statement truth:

- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.existsSubquery` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.includeWithWhere` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.leftJoinWithNull` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
- `demo.test.complex.staticGroupBy` -> `NO_SAFE_BASELINE_GROUP_BY`

Interpretation:

- `listOrdersWithUsersPaged` remains the primary semantic canary for paged dynamic-filter rewrites.
- `existsSubquery` is also a semantic canary. It must not be “fixed” by weakening `EXISTS` comparison semantics.
- `staticGroupBy` is no longer a generic candidate-selection target. It is a static group-by safe-baseline canary.
- `leftJoinWithNull` is not a candidate-selection target. It is an unsupported-strategy canary and should stay blocked unless an already-supported path exists.
- `includeWithWhere` stays in scope only as a safe-baseline canary; it should not be promoted by broad multi-fragment recovery.

## Batch10 Target Set

`batch10` should be the next five-statement blocker program:

1. `demo.order.harness.listOrdersWithUsersPaged`
2. `demo.test.complex.existsSubquery`
3. `demo.test.complex.leftJoinWithNull`
4. `demo.test.complex.staticGroupBy`
5. `demo.test.complex.includeWithWhere`

Why these five:

- They capture the next truthful mixed blocker set after `batch9`, without reopening already-classified blocked boundaries.
- `staticGroupBy` keeps a static group-by safe-baseline canary in scope.
- `listOrdersWithUsersPaged` and `existsSubquery` keep the semantic lane honest.
- `leftJoinWithNull` keeps the unsupported-strategy lane honest.
- `includeWithWhere` keeps the safe-baseline lane honest without reintroducing broad fragment/include promotion.

## Non-Goals

These stay out of scope and must not become collateral promotions:

- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`

## Success Standard

`batch10` is successful if it does one of the following safely:

- keeps the semantic canaries blocked, but with cleaner and more stable reasons
- keeps the unsupported-strategy and safe-baseline canaries blocked for the same truthful class of reason
- promotes `staticGroupBy` only through an already-supported safe-baseline path
- proves one of the five was mis-bucketed and moves it to a more honest blocker

`batch10` is not successful if it:

- weakens `JOIN`, `EXISTS`, or pagination semantics to manufacture green statements
- reclassifies unsupported-strategy tails into candidate-selection work
- broadens multi-fragment include recovery
- introduces a new patch family
