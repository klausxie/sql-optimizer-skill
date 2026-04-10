# Provider Strategy Decision Program

## Goal

Use the existing provider-quality research results to make an explicit product and investment decision for the choose-local lane.

This program does **not** repeat prompt research that has already been completed.

It converts the current evidence into one of four decisions:

- `freeze`
- `cross_model_trial`
- `fine_tune_investment`
- `abandon_choose_local_support`

## Starting Point

The following documents are now treated as completed research inputs, not open questions:

- [2026-04-10-provider-quality-research-program.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-research-program.md)
- [2026-04-10-provider-quality-failure-patterns.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-failure-patterns.md)
- [2026-04-10-provider-quality-experiment-matrix.csv](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-experiment-matrix.csv)
- [2026-04-10-provider-quality-per-run-classification.jsonl](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-per-run-classification.jsonl)
- [2026-04-10-provider-quality-recommendation.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-quality-recommendation.md)
- [2026-04-10-provider-candidate-quality-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-candidate-quality-review.md)

Current frozen conclusion:

- choose-local engineering substrate is ready
- `demo.user.advanced.findUsersByKeyword` still ends at `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- current-model prompt shaping has not produced a `branch_local_valid` candidate
- the current evidence points to a `model-limited` outcome, not a missing engineering capability

## Non-Goals

- Do not rerun the current-model prompt strictness experiments.
- Do not reopen scan / replay / patch-substrate work.
- Do not try to promote the sentinel inside this program.
- Do not weaken semantic, convergence, or patch-surface boundaries to manufacture a green result.

## Decision Questions

1. Is the current evidence already strong enough to freeze this lane?
2. Is a cross-model trial justified, or would it just repeat the same failure mode at higher cost?
3. Is a fine-tuning or synthetic-training investment justified by product value?
4. Is post-generation ranking/filtering worth doing, or is it just a cosmetic workaround?

## Decision Inputs

### Product Value

- Is choose-local support a hard requirement, or only a nice-to-have?
- What downstream value would a successful `findUsersByKeyword` promotion unlock?
- Are there more important unsupported lanes that compete for the same budget?

### Technical Evidence

- Current-model `branch_local_valid_rate`
- Stability of low-value and unsupported failure patterns
- Guardrail stability under stricter contracts
- Availability of alternative providers or stronger models

### Cost

- Estimated engineering time for cross-model evaluation
- Estimated infra and review cost for fine-tuning
- Long-term maintenance cost if a model-specific lane is introduced

## Decision Rubric

### 1. `freeze`

Choose this when:

- current evidence is already sufficient
- choose-local support is not important enough to justify model-side investment
- or product can accept the current boundary

Output:

- keep current blocked boundary
- document the lane as intentionally unsupported under current provider conditions

### 2. `cross_model_trial`

Choose this only when all of the following are true:

- choose-local support has clear product value
- at least one stronger or different provider is realistically available
- trial cost is low enough to justify a bounded experiment
- success would still fit the current engineering substrate

Bounded scope:

- at most 2 alternative models
- baseline contract only
- no new prompt research matrix

### 3. `fine_tune_investment`

Choose this only when:

- choose-local support is strategically important
- cross-model trial is unavailable or already failed
- there is a credible path to generating branch-local training examples
- the team accepts a larger model-quality investment

This is a new capability investment, not a continuation of prompt tuning.

### 4. `abandon_choose_local_support`

Choose this when:

- the product value is too low
- the model-side cost is too high
- or there are better capability investments available

This should be documented as a product decision, not a hidden engineering limitation.

## Program Stages

### Stage 1: Evidence Freeze

- Reconfirm that the research artifacts above are complete enough for decision-making.
- Summarize the decisive evidence in one compact table:
  - `branch_local_valid_rate`
  - dominant failure patterns
  - guardrail movement
  - recommendation from prior research

### Stage 2: Value And Cost Review

- Evaluate product importance of choose-local support.
- Compare it against at least two competing investments already visible in the project backlog.
- Estimate the smallest credible next-step cost for:
  - `cross_model_trial`
  - `fine_tune_investment`

### Stage 3: Decision Selection

- Choose exactly one of:
  - `freeze`
  - `cross_model_trial`
  - `fine_tune_investment`
  - `abandon_choose_local_support`

- Record why the other three were rejected.

### Stage 4: Next-Step Conversion

If the decision is:

- `freeze`
  - write a boundary memo and stop
- `cross_model_trial`
  - write a small execution plan with model list, budget, and stop condition
- `fine_tune_investment`
  - write an investment proposal with training-data requirements and expected cost
- `abandon_choose_local_support`
  - update the boundary delivery summary and stop

## Required Deliverables

- `provider_strategy_decision.md`
  - final chosen path and rationale
- `provider_strategy_comparison_table.md`
  - compared options with cost / value / risk
- optional follow-on plan only if the selected path requires more work

## Hard Stop

Stop this program immediately if it starts drifting back into:

- prompt wording iteration on the same current model
- engineering substrate tweaks
- exploratory batch work
- semantic-boundary weakening

That would mean the decision program has slipped back into unresolved research.

## Expected Outcome

By the end of this program, the project should no longer say:

> “provider quality is the next issue”

It should instead say one explicit thing:

> “we froze it,” or “we are funding a bounded cross-model trial,” or “we are making a model-training investment,” or “we are abandoning choose-local support.”
