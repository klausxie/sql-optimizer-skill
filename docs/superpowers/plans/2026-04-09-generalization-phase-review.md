# Generalization Phase Review

> **Scope:** Fresh replay review across `generalization-batch1..13`. This document is the phase closeout after the boundary-clarification pass; it is not a new implementation program.

## Fresh Baseline

Fresh replay runs used for this review:

- `generalization-batch1`: `run_787b2e28ed22`
- `generalization-batch2`: `run_e860c3d86d08`
- `generalization-batch3`: `run_5be669dce280`
- `generalization-batch4`: `run_6baea71f1466`
- `generalization-batch5`: `run_7f19604b924a`
- `generalization-batch6`: `run_82563e724b68`
- `generalization-batch7`: `run_144fa296fe28`
- `generalization-batch8`: `run_4316540eb4e1`
- `generalization-batch9`: `run_a2046676eede`
- `generalization-batch10`: `run_5500f2cabbd3`
- `generalization-batch11`: `run_776a8a490d93`
- `generalization-batch12`: `run_c52a2a41d9e6`
- `generalization-batch13`: `run_769cf66afcc2`

Fresh overall summary:

- `total_statements = 65`
- `AUTO_PATCHABLE = 6`
- `MANUAL_REVIEW = 59`
- `auto_patchable_rate = 0.0923`
- `ready_regressions = 0`
- `blocked_boundary_regressions = 0`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Fresh blocker bucket counts:

- `NO_SAFE_BASELINE_RECOVERY = 21`
- `NO_PATCHABLE_CANDIDATE_SELECTED = 16`
- `VALIDATE_STATUS_NOT_PASS = 10`
- `SEMANTIC_GATE_NOT_PASS = 9`
- `SHAPE_FAMILY_NOT_TARGET = 3`

## What Actually Improved

The phase did not produce a large new ready set. That is not a failure. The main improvement is that the blocker surface is now much more honest and much less generic.

Examples:

- candidate-selection tails are no longer lumped into a generic bucket:
  - `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`
  - `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
  - `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
  - `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`
- safe-baseline tails are now explicit:
  - `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
  - `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
  - `NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE`
  - `NO_SAFE_BASELINE_GROUP_BY`
- semantic overreach was reduced in at least one important case:
  - `demo.test.complex.existsSubquery` no longer sits in `SEMANTIC_PREDICATE_CHANGED`; it now lands in an honest unsupported-strategy lane.

This means the project moved from “many statements are blocked for vague reasons” to “most statements are blocked for explicit, reviewable reasons.”

## What Did Not Improve

The phase did not materially increase `AUTO_PATCHABLE`.

This is also an honest result:

- recent batches (`11`, `12`, `13`) are mostly boundary-clarification batches
- they repeatedly confirm that the remaining statements are blocked by:
  - missing safe-baseline recovery paths
  - validate/semantic boundaries
  - unsupported rewrite families

In other words, the project is no longer starved for classification work. It is now starved for product decisions about which blocked lanes should become supported.

## Phase Conclusion

The current phase should be treated as **complete**.

Reasoning:

1. The dominant blocker types are now stable.
2. Re-running more batches is producing mostly the same truth with different statement examples.
3. `ready_regressions = 0` and `blocked_boundary_regressions = 0`, so the current system is stable enough to stop exploratory batching.
4. Opening `batch14` immediately would likely continue the same pattern without changing the product boundary.

## What Happened Next

The recommended post-generalization cleanup stages were completed:

- [2026-04-09-safe-baseline-program-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)
- [2026-04-09-choose-aware-template-capability-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-choose-aware-template-capability-review.md)
- [2026-04-09-collection-predicate-capability-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-collection-predicate-capability-review.md)
- [2026-04-09-fragment-include-preservation-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-fragment-include-preservation-review.md)
- [2026-04-09-semantic-validation-boundary-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-review.md)
- [2026-04-09-unsupported-strategy-boundary-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-review.md)
- [2026-04-09-low-value-boundary-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-low-value-boundary-review.md)

## Current Recommendation

Do **not** open `batch14`.

Do **not** open another cleanup lane by default.

The project should now move to a final product-scope decision, summarized in:

- [2026-04-09-project-boundary-delivery-summary.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-project-boundary-delivery-summary.md)

From here, there are only two sensible options:

1. treat the current boundaries as the delivered scope
2. deliberately fund a new capability track

## Operational Rule For The Next Stage

The next stage should not be expressed as `batch14`, `batch15`, and so on.

It should be expressed as a **design/implementation program around one blocker family of product gaps**, with targeted sentinel statements reused as evidence, instead of continuing batch enumeration.
