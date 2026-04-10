# Generalization Batch13 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize broad include recovery, choose extension, or pagination semantic weakening.

**Goal:** Open the next generalization batch around the truthful non-candidate lanes visible after `batch12` fresh replay:

1. `NO_SAFE_BASELINE_RECOVERY`
2. `VALIDATE_STATUS_NOT_PASS`
3. `SEMANTIC_GATE_NOT_PASS`

This intake is intentionally a boundary-clarification batch. It is not designed to manufacture new `AUTO_PATCHABLE` statements.

## Fresh Program Baseline

Fresh replay run:

- `batch13`: `run_c5294ca22116`

Current `batch13` summary:

- `total_statements = 5`
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Per-statement truth:

- `demo.user.advanced.findUsersByKeyword` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

Interpretation:

- `findUsersByKeyword`, `findShipments`, and `multiFragmentLevel1` are now explicit safe-baseline subtype sentinels.
- `includeNested` remains the validate/semantic canary for nested include shapes.
- `listOrdersWithUsersPaged` remains the semantic canary for paged dynamic-filter rewrites.

## Batch13 Target Set

`batch13` should be the next five-statement blocker program:

1. `demo.user.advanced.findUsersByKeyword`
2. `demo.shipment.harness.findShipments`
3. `demo.test.complex.multiFragmentLevel1`
4. `demo.test.complex.includeNested`
5. `demo.order.harness.listOrdersWithUsersPaged`

Why these five:

- They capture the remaining truthful mixed boundary after `batch12`.
- Three statements pin the safe-baseline lane to explicit subtypes.
- One statement keeps validate/semantic behavior honest.
- One statement keeps the semantic lane honest.

## Non-Goals

These stay out of scope and must not become collateral promotions:

- `demo.test.complex.staticSimpleSelect`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.inSubquery`
- `demo.test.complex.leftJoinWithNull`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
- `demo.test.complex.fragmentInJoin`
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

`batch13` is successful if it does one of the following safely:

- keeps all five blocked, but with the same or cleaner truthful blocker subtypes
- proves one of the five was still mis-bucketed and moves it to a more honest blocker
- confirms that the current remaining work is boundary clarification, not new family expansion

`batch13` is not successful if it:

- weakens pagination or `EXISTS` semantics to manufacture green statements
- broadens multi-fragment include or choose-guarded recovery
- introduces a new patch family
