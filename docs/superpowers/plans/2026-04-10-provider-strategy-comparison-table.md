# Provider Strategy Comparison Table

## Context

This table converts the completed provider-quality research into an explicit option comparison for the choose-local lane.

Primary reference inputs:

- [2026-04-10-provider-quality-recommendation.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-recommendation.md)
- [2026-04-10-provider-quality-failure-patterns.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-failure-patterns.md)
- [2026-04-10-provider-quality-experiment-matrix.csv](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-experiment-matrix.csv)
- [2026-04-10-provider-quality-per-run-classification.jsonl](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-per-run-classification.jsonl)
- [2026-04-10-provider-candidate-quality-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-candidate-quality-review.md)

## Frozen Evidence

- primary sentinel: `demo.user.advanced.findUsersByKeyword`
- current-model strict contract result: `0% branch_local_valid`
- dominant failure patterns:
  - set operation rewrite
  - flattened predicate rewrite
  - default-branch reduction
  - canonical noop / low-value output
- engineering substrate is no longer the bottleneck
- current prompt-shaping evidence is already sufficient to conclude `model-limited`

## Option Comparison

| Option | Product Value | Cost | Risk | Expected Signal | Recommendation |
|---|---|---:|---:|---|---|
| `freeze` | preserves current delivered boundary with no further delay | low | low | immediately actionable | **recommended default** |
| `cross_model_trial` | moderate if choose-local support matters enough to fund one bounded check | medium | medium | can tell whether current outcome is provider-specific | second choice only if product explicitly wants choose-local |
| `fine_tune_investment` | potentially high, but only if choose-local support is strategically important | high | high | only valuable if business is willing to fund a model-quality track | not recommended now |
| `abandon_choose_local_support` | clear scope reduction, but removes future path | low | medium | strongest closure, weakest optionality | only if product explicitly wants hard scope cut |

## Why `freeze` Wins Right Now

### Evidence Strength

The current evidence is already strong enough for a product decision:

- no engineering blocker remains
- prompt-contract tightening did not improve results
- failure patterns are stable
- guardrails remained intact

### Opportunity Cost

The project has already completed:

- generalization boundary definition
- dynamic template substrate foundation
- provider-quality diagnosis

Continuing here would shift investment from product-capability engineering into model-quality research. That is a different class of work and should not be entered accidentally.

### Product Posture

Current project posture favors:

- explicit boundaries
- honest blocked outcomes
- deliberate new capability tracks only when product value is clear

That posture aligns with `freeze` much better than with open-ended provider experimentation.

## When `cross_model_trial` Becomes Justified

Only reopen the lane as a bounded cross-model trial if all of the following are true:

- choose-local support is explicitly valuable to product scope
- at least one materially different provider or stronger model is available
- the trial is capped to a small number of runs and models
- the team accepts that the likely outcome may still be "no support"

If any of those are false, `freeze` remains the correct decision.

## Rejected Paths

### Why not more prompt work?

Because that experiment has already been done.

The current-model prompt path has produced a stable `model-limited` result.

### Why not post-generation ranking/filtering?

Because the current failure mode is not ranking noise around one good candidate.

It is the absence of a promotable branch-local candidate at generation time.

### Why not fine-tune now?

Because that would be a new strategic investment without product justification yet.

The project should first decide whether choose-local support is worth that scale of investment.
