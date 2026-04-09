# Collection-Predicate Capability Review

## Verdict

No narrow, template-preserving collection-predicate safe path exists in current code.

The stage is complete and the collection-predicate lane should remain deferred.

## Why It Was Ruled Out

- the primary sentinel now has an explicit first-class capability profile:
  - `shapeFamily = FOREACH_COLLECTION_PREDICATE`
  - `capabilityTier = REVIEW_REQUIRED`
  - `patchSurface = WHERE_CLAUSE`
  - `blockerFamily = FOREACH_COLLECTION_GUARDED_PREDICATE`
- `safe_baseline_recovery_family(...)` still returns no baseline family for that shape
- `recover_candidates_from_shape(...)` has no collection-predicate recovery branch
- the real candidate pool still contains only:
  - canonical no-op advice
  - speculative dynamic-filter rewrites
- patch delivery still has no collection-predicate patch family or template-safe gate

That means the lane is now classified more honestly, but it is not promotable with the current capability surface.

## Code Evidence

- [rewrite_facts.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/rewrite_facts.py)
- [candidate_generation_support.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/candidate_generation_support.py)
- [candidate_generation_engine.py](/tmp/sqlopt-post-batch7/python/sqlopt/platforms/sql/candidate_generation_engine.py)
- [validate_convergence.py](/tmp/sqlopt-post-batch7/python/sqlopt/stages/validate_convergence.py)
- [convergence_registry.py](/tmp/sqlopt-post-batch7/python/sqlopt/stages/convergence_registry.py)

## Fresh Replay Review

Fresh replay run:

- `generalization-batch9` -> [run_c289c5571df3](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_c289c5571df3)

Observed truth:

- `demo.order.harness.findOrdersByUserIdsAndStatus`
  - `shapeFamily = FOREACH_COLLECTION_PREDICATE`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- `demo.shipment.harness.findShipmentsByOrderIds`
  - remained outside the promoted lane
- `demo.user.advanced.findUsersByKeyword`
  - remained `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `demo.order.harness.listOrdersWithUsersPaged`
  - remained `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.multiFragmentLevel1`
  - remained `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.shipment.harness.findShipments`
  - remained `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`

No statement became `AUTO_PATCHABLE`. No guardrail was widened accidentally.

## Recommendation

Do not continue exploratory collection-predicate batches.

Only reopen this lane if there is a product decision to build a dedicated collection-aware capability that can:

- preserve `foreach` structure directly
- preserve include boundaries end-to-end
- isolate scalar guard predicates without flattening dynamic templates
- add a real patch family and patch gate for collection predicates

Until then, the next capability stage should move to fragment/include preservation.
