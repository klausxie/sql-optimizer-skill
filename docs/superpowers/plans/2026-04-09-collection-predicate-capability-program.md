# Collection-Predicate Capability Program

## Goal

Execute the first post-choose capability stage by determining whether a narrow, template-aware collection-predicate path is viable.

This program starts from the completed safe-baseline review and the completed choose-aware review. It should not reopen new exploratory `batchN` intake. It should answer one bounded product question:

> can a safe, template-preserving capability be defined for dynamic collection predicates, or should the current lanes remain explicit boundaries?

## Why This Program Exists

The current roadmap is already clear:

- `choose-aware template capability` was re-deferred
- the next highest-value deferred subtype is `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- collection predicates are structurally important and likely more reusable than a bespoke choose-aware branch editor

The safe-baseline decision table already marked this lane as `DEFER`, not `FREEZE`. That means it deserves one focused capability program before it is pushed further back.

Reference decisions:

- [2026-04-09-safe-baseline-decision-table.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-safe-baseline-decision-table.md)
- [2026-04-09-safe-baseline-program-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)
- [2026-04-09-choose-aware-template-capability-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-choose-aware-template-capability-review.md)

## Primary Sentinel

- `demo.order.harness.findOrdersByUserIdsAndStatus`

Current truth:

- `MANUAL_REVIEW / NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`

This is the main statement that should determine whether the lane is promotable.

## Guardrail Sentinels

- `demo.shipment.harness.findShipmentsByOrderIds`
  - explicit `FOREACH + INCLUDE` boundary that should not be widened accidentally
- `demo.user.advanced.findUsersByKeyword`
  - choose-aware deferred lane that must not be “fixed by accident”
- `demo.order.harness.listOrdersWithUsersPaged`
  - semantic canary; must remain blocked if predicate semantics still drift
- `demo.test.complex.multiFragmentLevel1`
  - fragment/include preservation canary; must not be widened by collection work
- `demo.shipment.harness.findShipments`
  - speculative limit canary; must not be reclassified into the collection lane

## Program Question

Can we support a narrow, template-aware collection predicate capability that:

- preserves `foreach` structure
- preserves include boundaries
- edits only the predicate envelope or collection predicate body
- does not flatten dynamic constructs into plain SQL text
- does not weaken semantic validation boundaries

If yes, this should become a new capability path.

If no, the lane should be re-deferred or frozen with stronger evidence.

## Scope Boundaries

Allowed scope:

- `FOREACH + INCLUDE + WHERE`
- single collection predicate lane
- template-preserving edits only
- replay-based verification on existing sentinels

Out of scope:

- broad `FOREACH` support
- multi-fragment include preservation work
- choose-aware branch editing
- pagination-changing rewrites
- join-order / semantic relaxation
- new exploratory `batch14`

## Task 1: Freeze Current Collection-Predicate Truth

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`

Work:

- lock the primary sentinel and guardrail sentinel set for this capability stage
- ensure current truth stays explicit:
  - `findOrdersByUserIdsAndStatus` -> `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
  - `findShipmentsByOrderIds` remains a non-goal boundary

**Success standard:** implementation cannot accidentally widen plain `FOREACH`/include lanes while this capability is being explored.

## Task 2: Add Collection-Predicate Capability Profile

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/rewrite_facts.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_rewrite_facts.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`

Work:

- introduce an explicit collection-predicate capability/profile marker
- distinguish:
  - “supported collection predicate shape but no safe path exists”
  - from generic no-safe-baseline dynamic rewrite

**Success standard:** collection-predicate capability becomes a first-class reviewable concept, not just a blocker subtype.

## Task 3: Prototype One Template-Preserving Safe Path

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/`

Work:

- determine whether there is one narrow collection-predicate path that is:
  - template-preserving
  - semantically guardable
  - reusable beyond a single statement
- if yes, implement only that one path
- if no, do not widen heuristics; explicitly re-defer or freeze the lane

**Success standard:** one real path is either proven with code/tests or ruled out with code/tests.

## Task 4: Patch Surface And Delivery Guard

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_utils.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_safety.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/patch_generate.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/patch/`

Work:

- only if Task 3 proves a real safe path exists
- add the minimum patch surface needed to preserve collection-predicate structure
- block delivery if patch generation would flatten `foreach` or widen include scope

**Success standard:** any promoted path stays template-preserving end-to-end.

## Task 5: Fresh Replay Review

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-collection-predicate-capability-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-collection-predicate-capability-review.md`

Work:

- rerun the primary sentinel and guardrails in replay
- verify:
  - no ready regressions
  - `findShipmentsByOrderIds` remains blocked
  - `findUsersByKeyword` remains deferred
  - semantic canaries remain honest
- record whether the primary sentinel gained a safe path or remained deferred

**Success standard:** the stage ends with a yes/no verdict, not another vague backlog entry.

## Exit Criteria

This program is complete when:

1. collection-predicate capability is either promoted narrowly or re-deferred/frozen with stronger evidence
2. plain `FOREACH + INCLUDE` non-goal boundaries remain blocked
3. replay review confirms no regressions in choose, fragment/include, or semantic canaries
4. the next stage remains capability-driven, not another exploratory batch
