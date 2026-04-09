# Generalization Batch8 Intake

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans before implementation. This intake freezes the next batch scope only; it does not authorize widening blocked semantic-risk families.

**Goal:** Open the next generalization batch around the dominant truthful blockers after `batch1..7` fresh replay:

1. `NO_SAFE_BASELINE_RECOVERY`
2. `SEMANTIC_PREDICATE_CHANGED`
3. `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`

This intake explicitly avoids reopening:
- broad choose support
- plain `FOREACH/INCLUDE` predicate support
- fragment-chain / fragment-choose support
- join/exists semantic relaxations
- offset-to-keyset promotion

## Fresh Program Baseline

Fresh replay runs:

- `batch1`: `run_a41f38fc51b1`
- `batch2`: `run_9e3a10d5f614`
- `batch3`: `run_8d80dd50a50a`
- `batch4`: `run_9c7dad58b472`
- `batch5`: `run_3738d45a6557`
- `batch6`: `run_31c6fc054f3f`
- `batch7`: `run_915a2c2d0004`

Current overall summary:

- `total_statements = 35`
- `AUTO_PATCHABLE = 6`
- `MANUAL_REVIEW = 29`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Current dominant blocker counts:

- `NO_SAFE_BASELINE_RECOVERY = 8`
- `VALIDATE_SEMANTIC_ERROR = 7`
- `SEMANTIC_PREDICATE_CHANGED = 6`
- `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY = 3`
- `SHAPE_FAMILY_NOT_TARGET = 3`

## Batch8 Target Set

`batch8` should be the next five-statement blocker program:

1. `demo.user.advanced.findUsersByKeyword`
2. `demo.shipment.harness.findShipments`
3. `demo.order.harness.listOrdersWithUsersPaged`
4. `demo.test.complex.inSubquery`
5. `demo.test.complex.multiFragmentLevel1`

Why these five:

- `findUsersByKeyword` and `findShipments` are now clean `NO_SAFE_BASELINE_RECOVERY` sentinels.
- `listOrdersWithUsersPaged` is the clean `SEMANTIC_PREDICATE_CHANGED` sentinel.
- `inSubquery` is the narrow unsupported-strategy canary for `subquery_to_exists / subquery_to_join` wording drift; it belongs in the batch because it used to look semantic-risk but is actually candidate-lane cleanup.
- `multiFragmentLevel1` is still blocked by `NO_SAFE_BASELINE_RECOVERY` and gives a second template-heavy safe-baseline case without broadening fragment-chain support.

## Non-Goals

These stay as blocked boundaries and must not become collateral promotions:

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.findOrdersByNos`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentSeparate`
- `demo.test.complex.existsSubquery`
- `demo.test.complex.leftJoinWithNull`

## Success Standard

`batch8` is successful if it does one of the following safely:

- keeps the five targets blocked, but with cleaner and more stable reasons
- promotes one or more targets only through already-supported safe paths
- reduces ambiguity between `NO_SAFE_BASELINE_RECOVERY`, true semantic blockers, and unsupported-strategy candidate churn

`batch8` is not successful if it:

- introduces a new patch family
- relaxes semantic gates for convenience
- reclassifies semantic-risk statements into low-value candidate buckets
- weakens any listed non-goal boundary
