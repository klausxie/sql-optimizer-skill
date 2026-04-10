# Provider Strategy Decision

## Decision

The choose-local provider lane is now **frozen**.

This is a product and investment decision, not an engineering failure.

## Scope Of This Decision

This decision applies to the current choose-local primary sentinel:

- `demo.user.advanced.findUsersByKeyword`

It also applies to the current idea of continuing prompt-level iteration on the same provider/model path.

## Why This Decision Was Chosen

The completed provider-quality research already answered the key question:

> Is the remaining failure prompt-fixable, or is it model-limited?

Current evidence says:

- engineering substrate is ready
- branch-local contract is explicit
- prompt shaping did not produce a valid branch-local candidate
- the remaining failure mode is provider/model quality

The strongest direct statement remains the one in:

- [2026-04-10-provider-quality-recommendation.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-recommendation.md)

That recommendation is now accepted as the project decision.

## Rejected Alternatives

### `cross_model_trial`

Rejected for now.

Reason:

- it is a new investment, not a continuation of current engineering work
- current product scope does not yet justify reopening the lane
- this should only happen if product explicitly chooses to fund a bounded model comparison

### `fine_tune_investment`

Rejected for now.

Reason:

- it is too expensive relative to the current demonstrated value of choose-local support
- the project does not yet have a product mandate that would justify model-training work

### `abandon_choose_local_support`

Rejected for now.

Reason:

- the current boundary is better expressed as a freeze than a permanent abandonment
- future model-quality investment remains possible if product priorities change

## Operational Meaning

From this point forward:

- do not continue prompt tweaking on the current model
- do not reopen choose-local engineering substrate work
- do not reopen exploratory choose-local batches

The lane should remain documented as:

- engineering-ready
- provider-limited
- frozen pending explicit model-side investment

## Allowed Future Reopen Condition

This lane may be reopened only under one of these conditions:

1. product explicitly requests a bounded `cross_model_trial`
2. product explicitly funds a `fine_tune_investment`

Without one of those decisions, the correct next action is to leave the boundary in place.

## Project-Level Outcome

This decision keeps the project aligned with the boundary-first approach already established in:

- [2026-04-09-project-boundary-delivery-summary.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-project-boundary-delivery-summary.md)
- [2026-04-10-provider-strategy-comparison-table.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-strategy-comparison-table.md)

The project should not spend more engineering time trying to force choose-local promotion on the current provider path.

## Status

- `DECISION = freeze`
- `CHOOSE_LOCAL_LANE = provider-limited`
- `NEXT_ALLOWED_STEP = explicit model-side investment only`
