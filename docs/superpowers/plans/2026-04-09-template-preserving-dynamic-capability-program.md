# Template-Preserving Dynamic Capability Program

## Why This Is The Right Next Stage

The project has already finished:

- family exploration
- generalization batching
- safe-baseline subtype review
- semantic / validation boundary clarification
- unsupported-strategy freeze
- low-value / no-op freeze

The remaining deferred lanes now point to the same missing capability surface:

- `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`

Both are blocked for the same structural reason:

- current dynamic safe-baseline logic expects statement-level template-safe paths
- current patch delivery has no branch-local / collection-local dynamic patch surface
- current candidate recovery cannot preserve `<choose>` / `<foreach>` structure end-to-end

So the next stage should not be `batch14`, `choose v2`, or `collection v2` in isolation.

It should be a single funded program that builds the minimum template-preserving dynamic capability foundation needed to make those lanes revisit-able.

## Program Goal

Build the smallest viable dynamic template-preserving capability layer that can answer this product question honestly:

> Can the system support one narrow dynamic branch-local or collection-local patch path without flattening MyBatis structure?

This program is about enabling that answer, not about promising broad dynamic support.

## Recommendation

Run this program as a foundation-first investment with one prototype target:

1. build the dynamic patch-surface foundation
2. prototype `CHOOSE_BRANCH_BODY` first
3. only then reassess whether `FOREACH_COLLECTION_PREDICATE` should be attempted

## Primary Prototype Sentinel

- `demo.user.advanced.findUsersByKeyword`

## Deferred Second-Wave Sentinel

- `demo.order.harness.findOrdersByUserIdsAndStatus`

## Guardrails

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

## Work Plan

### Task 1: Freeze Dynamic Foundation Evidence

Capture the exact current truth for:

- `findUsersByKeyword`
- `findOrdersByUserIdsAndStatus`
- all choose / collection guardrails

### Task 2: Define A Formal Dynamic Patch-Surface Contract

Design a new internal contract for dynamic template-safe editing, centered on:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

### Task 3: Add Review-Only Plumbing For The New Surface

Implement the smallest end-to-end plumbing so the system can carry the new patch surface through:

- rewrite facts
- candidate generation metadata
- validate convergence
- patch gating

Keep it review-only first.

### Task 4: Prototype `CHOOSE_BRANCH_BODY`

Attempt one narrow prototype on:

- `demo.user.advanced.findUsersByKeyword`

Strict limits:

- one top-level `<choose>` only
- directly under `<where>`
- branch bodies must remain predicate-only
- no include/order/group/having/join/union/limit support

### Task 5: Reassess Collection-Predicate On Top Of The Same Surface

Only if Task 4 establishes a viable patch-surface contract.

### Task 6: Fresh Replay Review And Final Verdict

Run fresh replay on:

- primary prototype sentinel
- collection sentinel
- all dynamic guardrails

## Exit Rule

This program should end as soon as one of these is proven:

1. `CHOOSE_BRANCH_BODY` can be supported narrowly and honestly
2. even the narrowest dynamic patch-surface prototype is still not worth supporting
