# Surface-Specific Dynamic Decision Table

## Purpose

Freeze the current product decision for dynamic sub-statement template-preserving surfaces before deeper implementation work begins.

This table is the source of truth for:

- which dynamic surfaces are recognized
- which remain review-only
- which sentinel owns each surface
- what promotion would require
- which guardrails must remain blocked

## Decision Table

| Surface | Current Status | Primary Sentinel | Current Blocker Truth | Promotion Bar | Current Recommendation |
| --- | --- | --- | --- | --- | --- |
| `CHOOSE_BRANCH_BODY` | Review-only | `demo.user.advanced.findUsersByKeyword` | `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` after choose-local render identity is provided to optimize | requires branch-local rewrite op, replay contract, patch family, materialization mode, and a non-speculative candidate source | `DEFER` |
| `COLLECTION_PREDICATE_BODY` | Review-only | `demo.order.harness.findOrdersByUserIdsAndStatus` | `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE` | requires collection-local rewrite op, replay contract, patch family, and materialization mode | `DEFER` |
| `WHERE_CLAUSE` | Existing generic review lane | none for new investment | generic dynamic review-only cases | no new investment in this program | `MAINTAIN` |
| `SET_CLAUSE` | Existing generic review lane | none for new investment | dynamic set-template review-only cases | no new investment in this program | `MAINTAIN` |
| `STATEMENT_BODY` | Existing supported/review mixed lane | not part of this program | already governed by existing dynamic statement rules | not in scope here | `OUT_OF_SCOPE` |

## Sentinel Ownership

### Primary Prototype Sentinel

- `demo.user.advanced.findUsersByKeyword`
  - owns `CHOOSE_BRANCH_BODY`
  - must remain blocked unless a narrow choose-local path is proven safe

### Second-Wave Sentinel

- `demo.order.harness.findOrdersByUserIdsAndStatus`
  - owns `COLLECTION_PREDICATE_BODY`
  - must remain blocked unless choose-local prototype succeeds first

## Guardrails

These statements must remain blocked while this program is in design or review-only plumbing mode:

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

## Promotion Preconditions

Neither `CHOOSE_BRANCH_BODY` nor `COLLECTION_PREDICATE_BODY` may be promoted unless all of the following exist:

1. a surface-specific rewrite op
2. a surface-specific replay contract
3. a surface-specific patch family
4. a surface-specific materialization mode
5. sentinel replay evidence proving no guardrail widening

If any one of these is missing, the surface remains review-only.

## Ordering Rule

Promotion attempts must happen in this order:

1. `CHOOSE_BRANCH_BODY`
2. `COLLECTION_PREDICATE_BODY`

Collection is second-wave by design. It must not be promoted by analogy from generic foreach support.

## No-Go Signals

The program must stop and keep the surface deferred if any of these becomes true:

- the proposed rewrite op requires statement-level fallback
- the proposed rewrite op requires fragment-level fallback
- replay cannot prove surface-local target identity
- patch generation would need to widen to whole-statement or whole-fragment replacement
- a guardrail starts passing only because surface boundaries became ambiguous

## Current Product Decision

As of this phase:

- `CHOOSE_BRANCH_BODY = review-only, deferred`
- `COLLECTION_PREDICATE_BODY = review-only, deferred`

The current investment decision is:

- foundation work is allowed
- review-only plumbing is allowed
- narrow choose prototype is conditionally allowed only after substrate completion
- collection reassessment is forbidden unless choose prototype succeeds cleanly
