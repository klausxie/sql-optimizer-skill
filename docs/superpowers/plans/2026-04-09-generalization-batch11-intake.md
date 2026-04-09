# Generalization Batch11 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize widening `EXISTS` / pagination semantics, broad multi-fragment include recovery, or new patch families.

**Goal:** Freeze the truthful mixed lane after `batch11` fresh replay and hand off the next intake without broadening semantic or include boundaries.

1. `NO_PATCHABLE_CANDIDATE_SELECTED`
2. `SEMANTIC_GATE_NOT_PASS`
3. `NO_SAFE_BASELINE_RECOVERY`

This intake keeps one safe-baseline canary and one low-value candidate canary inside scope so semantic work does not accidentally blur other blocked boundaries.

This intake explicitly avoids reopening:
- broad `EXISTS` semantic relaxation
- pagination / `OFFSET` semantic weakening
- generic nested-include recovery
- generic multi-fragment include recovery
- new patch families for `include`, `exists`, or static group-by rewrites

## Fresh Program Baseline

Fresh replay runs:

- `batch10`: `run_7cdb98d1eb49`
- `batch11`: `run_2fdcb5d7df7b`

Current `batch11` summary:

- `total_statements = 5`
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_PATCHABLE_CANDIDATE_SELECTED`
- `recommended_next_step = fix_shared_candidate_selection_gaps`

Per-statement truth:

- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
- `demo.test.complex.fragmentInJoin` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.staticSimpleSelect` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

Interpretation:

- `listOrdersWithUsersPaged` remains the primary semantic canary for paged dynamic-filter rewrites.
- `existsSubquery` is no longer a semantic blocker. It is now a candidate-selection/unsupported-strategy canary after the narrow redundant `id IS NOT NULL` semantic override.
- `includeNested` is not a candidate-selection target. It is a validate/semantic canary for nested include shapes.
- `fragmentInJoin` stays in scope only as a safe-baseline canary; it should not be promoted by broad multi-fragment include recovery.
- `staticSimpleSelect` and `existsSubquery` are now the two clean candidate-selection canaries in this batch.

## Batch11 Target Set

`batch11` should be the next five-statement blocker program:

1. `demo.test.complex.fragmentInJoin`
2. `demo.test.complex.staticSimpleSelect`
3. `demo.test.complex.includeNested`
4. `demo.order.harness.listOrdersWithUsersPaged`
5. `demo.test.complex.existsSubquery`

Why these five:

- They capture the next truthful mixed blocker set after `batch10`.
- `listOrdersWithUsersPaged` keeps the semantic lane honest.
- `existsSubquery` keeps the unsupported-strategy lane honest.
- `includeNested` keeps the validate/semantic lane honest for nested include shapes.
- `fragmentInJoin` keeps the safe-baseline lane honest without reopening broad fragment/include promotion.
- `staticSimpleSelect` keeps one shared low-value candidate canary in scope.

## Non-Goals

These stay out of scope and must not become collateral promotions:

- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
- `demo.test.complex.includeWithWhere`
- `demo.test.complex.staticGroupBy`
- `demo.test.complex.leftJoinWithNull`
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`

## Success Standard

`batch11` is successful if it does one of the following safely:

- keeps the mixed candidate/semantic/validate/safe-baseline canaries blocked, but with cleaner and more stable reasons
- keeps the validate/semantic, safe-baseline, and low-value canaries blocked for the same truthful class of reason
- proves one of the five was mis-bucketed and moves it to a more honest blocker
- promotes `staticSimpleSelect` only through an already-supported path

`batch11` is not successful if it:

- weakens `EXISTS` or pagination semantics to manufacture green statements
- broadens nested-include or multi-fragment include recovery
- reclassifies semantic-risk statements into candidate-selection work
- introduces a new patch family
