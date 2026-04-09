# Safe-Baseline Decision Table

> **Status:** Initial formal decision table for the post-generalization safe-baseline stage. This document turns the current `NO_SAFE_BASELINE_*` blocker set into explicit product dispositions. It is intentionally opinionated.

## Decision Rule

Each subtype is evaluated against the same four questions:

1. Can we define a narrow template-aware rewrite that preserves semantics?
2. Can existing validate / semantic checks verify that rewrite without broad new machinery?
3. Does the change fit an existing family/recovery path, or would it require a genuinely new capability?
4. Would supporting it improve a reusable lane, or just one isolated statement?

Disposition values:

- `PROMOTE`
  Build or prototype a real supported path now.
- `FREEZE`
  Treat as current non-goal / explicit blocked boundary.
- `DEFER`
  Plausible future capability, but not justified in the current stage.

## Decision Table

| Subtype | Sentinel | Current Truth | Disposition | Rationale | Next Action |
| --- | --- | --- | --- | --- | --- |
| `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER` | `demo.user.advanced.findUsersByKeyword` | Dynamic filter shape is recognized and semantics pass, but `rewrite_facts` still reports `capabilityTier = REVIEW_REQUIRED`, `baselineFamily = None`, and blocker `DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE`; current `SAFE_BASELINE_RECOVERY` only admits static families. | `DEFER` | This is still a plausible future capability, but not with the current patch/validator model. Supporting it would require a genuinely new template-aware patch path that preserves `<choose>` branches, not a small recovery rule. | Defer to a future choose-aware capability program; keep blocked under explicit subtype. |
| `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY` | `demo.shipment.harness.findShipments` | Remaining suggestions are speculative pagination / limit style rewrites, not conservative structural recovery. | `FREEZE` | A “safe baseline” that depends on adding/changing pagination is not really a baseline. Promoting this would mainly weaken semantics to chase green status. | Freeze as current non-goal and keep blocked under explicit subtype. |
| `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE` | `demo.test.complex.multiFragmentLevel1` | Multi-fragment include chains remain structurally complex and repeatedly resist template-safe patching. | `FREEZE` | Current patch model is not strong enough at fragment-chain preservation. Continuing to treat this as “missing baseline work” is misleading; it is a product boundary for now. | Freeze as boundary; revisit only in a dedicated fragment/template capability stage. |
| `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE` | `demo.order.harness.findOrdersByUserIdsAndStatus` | Real dynamic collection predicate path with scalar guards, but support would require template-aware handling across `foreach + include + where`. | `DEFER` | This is important, but it is not a small baseline tweak. It deserves its own capability track rather than being forced into the current safe-baseline stage. | Defer to a future collection-predicate capability program. |
| `NO_SAFE_BASELINE_GROUP_BY` | `demo.test.complex.staticGroupBy` | Group-by safe-baseline gap appears closer to aggregate capability design than to recovery cleanup. | `FREEZE` | Current aggregate families are already sharp. Treating group-by as “just another baseline gap” risks blurring a more deliberate aggregate roadmap. | Freeze for this stage; keep blocked under explicit subtype. |

## Summary Decision

This stage will not try to solve all safe-baseline subtypes.

It will do exactly this:

1. `FREEZE`
   - `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
   - `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
   - `NO_SAFE_BASELINE_GROUP_BY`
2. `DEFER`
   - `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
   - `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`

## Why This Is The Right Split

This split keeps the program honest:

- three subtypes are better treated as explicit product boundaries
- two subtypes are important, but clearly belong to different future capability tracks

That avoids the trap of pretending every `NO_SAFE_BASELINE_*` subtype is “nearly supported.”

## Immediate Consequences

1. The stage should not spend engineering time trying to auto-patch speculative-limit or multi-fragment-include cases.
2. `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER` should stay visible, but move to a future choose-aware capability track instead of pretending a small recovery rule is enough.
3. `FOREACH_INCLUDE_PREDICATE` should stay visible, but it should not block this stage from completing.
