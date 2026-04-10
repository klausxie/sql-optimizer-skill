# Provider Candidate Quality Handoff

## Purpose

This document hands off the next stage of work for the choose-local lane.

The engineering substrate is now good enough.

The remaining blocker is provider candidate quality.

The next agent should not spend time rebuilding scan, replay, patching, or local-surface substrate unless new evidence proves one of those layers is still broken.

## Branch And Workspace

- Worktree: `/tmp/sqlopt-template-dynamic-capability`
- Branch: `codex/template-preserving-dynamic-capability`

## Frozen Conclusion

The current choose-local lane is closed from an engineering-substrate perspective.

What is already true:

- `CHOOSE_BRANCH_BODY` is a real local surface
- local choose materialization exists
- local choose patch build exists
- local choose replay exists
- scan/catalog now emit `dynamicRenderIdentity`
- optimize prompt and replay fingerprinting now include a choose-local surface contract

What is still false:

- the primary sentinel does not receive a promotable branch-local rewrite candidate

Current truthful outcome for the primary sentinel:

- `demo.user.advanced.findUsersByKeyword`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

This is not a replay miss anymore.

It is not a missing scan identity problem anymore.

It is not a missing choose-local patch substrate problem anymore.

It is a provider-output-quality problem.

## Primary Sentinel

- `demo.user.advanced.findUsersByKeyword`

Why this statement matters:

- It is the narrowest real sample-project choose-local case we have
- It now carries branch-local render identity
- It is the one statement that should become promotable first if choose-local support is ever going to work

## Guardrails

These must remain blocked while provider-quality work proceeds:

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.shipment.harness.findShipments`
- `demo.shipment.harness.findShipmentsByOrderIds`
- `demo.test.complex.multiFragmentLevel1`
- `demo.test.complex.includeNested`
- `demo.user.findUsers`

The provider-quality program is not allowed to widen these by weakening semantic rules or by reintroducing statement-level fallback.

## Most Important Evidence

### Fresh replay truth

These runs already reflect the final choose-local engineering state plus the stricter provider contract:

- `generalization-batch9`: [run_0bba13603075](/tmp/sqlopt-template-dynamic-capability/tests/fixtures/projects/sample_project/runs/run_0bba13603075)
- `generalization-batch13`: [run_5662aef54d87](/tmp/sqlopt-template-dynamic-capability/tests/fixtures/projects/sample_project/runs/run_5662aef54d87)

In both runs:

- `shapeFamily = IF_GUARDED_FILTER_STATEMENT`
- `convergenceDecision = MANUAL_REVIEW`
- `conflictReason = NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

### Targeted record cassette

This cassette is the most important artifact for the next agent:

- normalized: [f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json](/tmp/sqlopt-template-dynamic-capability/tests/fixtures/llm_cassettes/optimize/normalized/f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json)
- raw: [f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json](/tmp/sqlopt-template-dynamic-capability/tests/fixtures/llm_cassettes/optimize/raw/f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json)

That cassette proves:

- the provider saw `dynamicRenderIdentity`
- the provider saw `chooseBranchSurfaces`
- the provider saw the new choose-local `dynamicSurfaceContract`
- the provider still returned only low-value candidates

Returned candidate strategies:

- `INDEX_SEEK`
- `PREDICATE_SIMPLIFICATION`
- `PREDICATE_REDUCTION`

The candidate texts are still wrong for promotion:

- one rewrites to `UNION ALL`
- one rewrites the flattened OR predicate
- one drops back to the default filter

None of them is a true branch-local cleanup.

## Current Prompt Contract

The choose-local optimize contract is now explicit in [optimizer_sql.py](/tmp/sqlopt-template-dynamic-capability/python/sqlopt/platforms/sql/optimizer_sql.py).

Current `dynamicSurfaceContract` fields:

- `targetSurface = CHOOSE_BRANCH_BODY`
- `branchLocalOnly = true`
- `forbidSetOperations = true`
- `forbidBranchMerge = true`
- `forbidWholeStatementRewrite = true`
- `allowedTemplateRewriteOps = ["replace_choose_branch_body"]`
- `preferredOutcome = BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE`

This contract is also part of replay fingerprinting in [llm_cassette.py](/tmp/sqlopt-template-dynamic-capability/python/sqlopt/platforms/sql/llm_cassette.py).

So if the next agent changes prompt wording or contract shape, a reseed is required.

## What Was Already Proven

These engineering questions are already answered:

1. Can scan identify the rendered choose branch?
   - Yes.

2. Can optimize receive branch-local identity?
   - Yes.

3. Can replay fingerprinting distinguish old vs new choose-local context?
   - Yes.

4. Can patch substrate handle a true `CHOOSE_BRANCH_BODY` local op?
   - Yes, for localizable choose shapes.

5. Is the current blocker still “missing safe-baseline contract”?
   - No.

The next agent should assume the above unless they find contrary evidence.

## Recommended Scope For The Next Agent

Only investigate provider candidate quality.

Good targets:

- prompt wording for candidate-generation task
- stronger negative instructions for banned rewrite shapes
- narrower definition of acceptable output
- model-specific steering if the provider supports it
- candidate post-filtering only if it creates a more truthful blocker, not fake promotion

Bad targets:

- more scan work
- more replay substrate work
- more patch-substrate work
- re-opening broad choose support
- relaxing semantic or convergence rules to manufacture green results

## Recommended First Tasks

1. Read the current provider review:
   - [2026-04-09-surface-specific-dynamic-capability-review.md](/tmp/sqlopt-template-dynamic-capability/docs/superpowers/plans/2026-04-09-surface-specific-dynamic-capability-review.md)

2. Inspect the current choose-local cassette:
   - normalized and raw `f2378d...`

3. Inspect the current optimize prompt builder:
   - [optimizer_sql.py](/tmp/sqlopt-template-dynamic-capability/python/sqlopt/platforms/sql/optimizer_sql.py)

4. Inspect the low-value classification for the sentinel:
   - [candidate_generation_engine.py](/tmp/sqlopt-template-dynamic-capability/python/sqlopt/platforms/sql/candidate_generation_engine.py)
   - [test_candidate_generation_engine.py](/tmp/sqlopt-template-dynamic-capability/tests/unit/sql/test_candidate_generation_engine.py)

5. Make one narrow provider-quality change, then:
   - reseed `generalization-batch9` with `--llm-mode record`
   - replay `generalization-batch9`
   - replay `generalization-batch13`

6. Stop immediately if the result is still low-value-only after one coherent shaping pass.

## Hard Stop Conditions

The next agent should stop and report instead of continuing if any of these happens:

- provider still returns only non-local or speculative candidates after one coherent prompt-contract revision
- the only way to get a green result is to weaken semantic or replay boundaries
- a guardrail starts moving because the surface boundary became ambiguous
- the change would require statement-level or fragment-level fallback

If any stop condition triggers, the correct next step is another product decision, not more local engineering tweaks.

## Minimal Verification Commands

Use these first:

```bash
python3 -m pytest -q \
  tests/unit/sql/test_optimize_proposal.py \
  tests/unit/sql/test_llm_cassette.py \
  tests/unit/sql/test_candidate_generation_engine.py \
  tests/unit/verification/test_validate_convergence.py \
  tests/ci/test_generalization_summary_script.py \
  -k 'dynamic_surface_contract or choose_local_rewrite_constraints or find_users_by_keyword_candidate_pool_classification_after_branch_identity_reseed or keeps_choose_guarded_safe_baseline_gap_without_branch_identity or choose_guarded_low_value_only_after_identity_reseed or batch9_only_exposes_safe_baseline_focus_and_sentinels or batch13_returns_to_safe_baseline_focus'
```

Then run:

```bash
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --llm-mode record --max-seconds 240
python3 scripts/ci/generalization_refresh.py --batch generalization-batch9 --max-seconds 240
python3 scripts/ci/generalization_refresh.py --batch generalization-batch13 --max-seconds 240
```

## Final Handoff Statement

The next agent is not inheriting a broken choose-local implementation.

The next agent is inheriting a functioning choose-local engineering substrate whose remaining failure mode is:

> the provider still does not emit a promotable branch-local cleanup candidate for the primary sentinel, even when given explicit choose-local surface identity and rewrite constraints.
