# Provider Candidate Quality Baseline Audit

## Purpose

This document freezes the starting truth for the provider-quality program.

The choose-local engineering substrate is no longer the bottleneck.

The current bottleneck is provider candidate quality for the primary sentinel.

## Primary Sentinel

- `demo.user.advanced.findUsersByKeyword`

Current truthful outcome:

- `shapeFamily = IF_GUARDED_FILTER_STATEMENT`
- `convergenceDecision = MANUAL_REVIEW`
- `conflictReason = NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

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

## Current Provider Contract

Source:

- [optimizer_sql.py](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/python/sqlopt/platforms/sql/optimizer_sql.py)

Current `dynamicSurfaceContract` for choose-local optimize requests:

- `targetSurface = CHOOSE_BRANCH_BODY`
- `branchLocalOnly = true`
- `forbidSetOperations = true`
- `forbidBranchMerge = true`
- `forbidWholeStatementRewrite = true`
- `allowedTemplateRewriteOps = ["replace_choose_branch_body"]`
- `preferredOutcome = BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE`

## Most Important Evidence

### Targeted record cassette

- normalized:
  [f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json](/Users/klaus/.config/superpowers/worktrees/sql-optimizer-skill/codex-provider-candidate-quality-program/tests/fixtures/llm_cassettes/optimize/normalized/f2378d949f6dff98af8cb746d090b03a913528d3f0f610e9cf986ff1c8dbcced.json)

The cassette proves the provider already sees:

- `dynamicRenderIdentity`
- `chooseBranchSurfaces`
- the explicit choose-local `dynamicSurfaceContract`

### Current returned candidate strategies

- `INDEX_SEEK`
- `PREDICATE_SIMPLIFICATION`
- `PREDICATE_REDUCTION`

### Why they are still low-value

- `INDEX_SEEK` rewrites into `UNION ALL`, which violates the local-surface contract
- `PREDICATE_SIMPLIFICATION` rewrites the flattened statement predicate instead of a branch-local surface
- `PREDICATE_REDUCTION` collapses to the default filter and drops the branch-local cleanup objective

## Current Baseline Conclusion

The provider-quality program starts from this conclusion:

- prompt and replay contract are already explicit
- cassette reseeding already happened once under the stronger choose-local contract
- provider still emits only low-value candidates

This means the next change should be a narrow provider-shaping revision, not more scan/replay/patch engineering.

## Allowed Next-Step Scope

Allowed:

- optimize prompt wording
- stricter output contract wording
- provider-side negative constraints
- scoring or diagnostics that classify returned candidates more truthfully

Not allowed:

- weakening semantic rules
- reintroducing statement-level fallback
- broadening choose support outside the primary sentinel
- rebuilding scan or patch substrate

## Stop Condition

If one coherent provider-shaping revision still yields only low-value candidates for the primary sentinel, stop this line and report:

- engineering substrate is ready
- provider quality remains insufficient
- further progress requires a dedicated provider/model-quality investment
