# Safe-Baseline Program Review

## Scope

This review closes the `Safe-baseline design program` after the fresh replay verification pass.

Replay runs used as evidence:

- `generalization-batch1` -> `run_31334ba0edf5`
- `generalization-batch2` -> `run_d2b0b225cba2`
- `generalization-batch9` -> `run_1933c9afedf6`
- `generalization-batch10` -> `run_b66b40de215f`
- `generalization-batch13` -> `run_a2e70e3eac95`

## Fresh Replay Verdict

The safe-baseline stage is complete.

It did not produce a new auto-patchable subtype, but it did convert the remaining `NO_SAFE_BASELINE_*` surface from an exploratory backlog into explicit product decisions:

- `FREEZE`
  - `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
  - `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `NO_SAFE_BASELINE_GROUP_BY`
- `DEFER`
  - `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
  - `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`

## What The Replay Pass Proved

### Ready Sentinels Stayed Ready

The known ready sentinels still pass without regression:

- `demo.user.countUser`
- `demo.test.complex.fromClauseSubquery`
- `demo.test.complex.wrapperCount`

Fresh replay evidence:

- `generalization-batch1`: `2 AUTO_PATCHABLE`
- `generalization-batch2`: `1 AUTO_PATCHABLE`
- `ready_regressions = 0`

### Frozen/Deferred Safe-Baseline Lanes Stayed Blocked

The current safe-baseline blockers remained stable and explicit:

- `demo.user.advanced.findUsersByKeyword`
  - `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `demo.shipment.harness.findShipments`
  - `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `demo.test.complex.multiFragmentLevel1`
  - `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
  - `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`
- `demo.test.complex.staticGroupBy`
  - `NO_SAFE_BASELINE_GROUP_BY`

The semantic canary also remained honest:

- `demo.order.harness.listOrdersWithUsersPaged`
  - `SEMANTIC_PREDICATE_CHANGED`

Fresh replay evidence:

- `generalization-batch9`: `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `generalization-batch10`: `staticGroupBy -> NO_SAFE_BASELINE_GROUP_BY`
- `generalization-batch13`: `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `blocked_boundary_regressions = 0`

## Why `CHOOSE_GUARDED_FILTER` Was Deferred Instead Of Promoted

The sentinel `demo.user.advanced.findUsersByKeyword` proved that this is not a small recovery-rule gap:

- semantic validation passes
- shape family is already recognized as `IF_GUARDED_FILTER_STATEMENT`
- `rewrite_facts` still report:
  - `capabilityTier = REVIEW_REQUIRED`
  - `baselineFamily = None`
  - blocker `DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE`
- `SAFE_BASELINE_RECOVERY` only admits static-family baselines today

That means promotion would require a genuinely new choose-aware template-preserving patch capability, not a narrow extension to the current safe-baseline machinery.

## Final Stage Verdict

This stage should end here.

It successfully answered the product question:

- which safe-baseline subtypes are explicit current boundaries
- which ones belong to future capability tracks

It should not reopen `batch14`.

The next stage should be capability-driven, not another exploratory batch:

- a future choose-aware template capability program
- a future collection-predicate capability program
- or a fragment/include preservation program
