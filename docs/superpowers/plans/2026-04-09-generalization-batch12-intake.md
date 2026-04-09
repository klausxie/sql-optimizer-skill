# Generalization Batch12 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize widening pagination semantics, `EXISTS` rewrites, or JOIN/null-elimination semantics.

**Goal:** Open the next generalization batch around the truthful candidate-selection lane visible after `batch11` fresh replay:

1. `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
2. `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
3. `SEMANTIC_GATE_NOT_PASS`

This intake keeps one semantic canary inside scope so candidate-selection work does not accidentally blur a known semantic boundary.

This intake explicitly avoids reopening:
- pagination / `OFFSET` semantic weakening
- broad `EXISTS` semantic relaxation
- join null-elimination equivalence
- new patch families for `EXISTS`, `JOIN`, or nested include shapes

## Fresh Program Baseline

Fresh replay runs:

- `batch11`: `run_2fdcb5d7df7b`
- `batch12`: `run_a344702c1794`

Current `batch12` summary:

- `total_statements = 5`
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`
- `recommended_next_step = fix_shared_candidate_selection_gaps`

Per-statement truth:

- `demo.test.complex.staticSimpleSelect` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `demo.test.complex.inSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `demo.test.complex.leftJoinWithNull` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

Interpretation:

- `staticSimpleSelect` is the only clean low-value canary in this batch.
- `existsSubquery`, `inSubquery`, and `leftJoinWithNull` are all honest unsupported-strategy canaries, and each now carries its own subtype; they should not be “fixed” by inventing new patch families.
- `listOrdersWithUsersPaged` remains the semantic canary for paged dynamic-filter rewrites.

## Batch12 Target Set

`batch12` should be the next five-statement blocker program:

1. `demo.test.complex.staticSimpleSelect`
2. `demo.test.complex.existsSubquery`
3. `demo.test.complex.inSubquery`
4. `demo.test.complex.leftJoinWithNull`
5. `demo.order.harness.listOrdersWithUsersPaged`

Why these five:

- They capture the next truthful candidate-selection-heavy lane after `batch11`.
- `existsSubquery`, `inSubquery`, and `leftJoinWithNull` cluster the unsupported-strategy problem in one batch.
- `staticSimpleSelect` keeps one low-value candidate canary in scope.
- `listOrdersWithUsersPaged` keeps the semantic lane honest while the batch focuses on candidate selection.

## Non-Goals

These stay out of scope and must not become collateral promotions:

- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
- `demo.test.complex.fragmentInJoin`
- `demo.test.complex.includeNested`
- `demo.test.complex.includeWithWhere`
- `demo.test.complex.staticGroupBy`
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`

## Success Standard

`batch12` is successful if it does one of the following safely:

- keeps the unsupported-strategy, low-value, and semantic canaries blocked, but with cleaner and more stable reasons
- proves one of the unsupported-strategy statements was mis-bucketed and moves it to a more honest blocker
- promotes `staticSimpleSelect` only through an already-supported path

`batch12` is not successful if it:

- weakens pagination or `EXISTS` semantics to manufacture green statements
- turns unsupported-strategy statements into fake low-value candidates
- introduces a new patch family
