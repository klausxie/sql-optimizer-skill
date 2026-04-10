# Surface-Specific Dynamic Capability Review

## Verdict

This program produced a useful substrate definition.

It did not produce a promotable dynamic surface.

Final status:

- `FOUNDATION = yes`
- `REVIEW_ONLY_PLUMBING = yes`
- `CHOOSE_LOCAL_SUBSTRATE = yes`
- `NARROW_CHOOSE_PROMOTION = no`
- `COLLECTION_REASSESSMENT = not_started`
- `PROVIDER_CONTRACT_TRIAL = completed`
- `PROGRAM_RESULT = defer`

## What This Program Added

### 1. Surface-specific dynamic substrate is now explicitly modeled

The project now has explicit program artifacts for:

- the investment decision table
- surface-specific rewrite ops
- surface-specific replay contract
- surface-specific patch family and materialization contract

These are no longer informal ideas.

They are now written down as concrete internal contracts.

### 2. Review-only plumbing is real

The pipeline can now carry honest review-only dynamic surface metadata for:

- `CHOOSE_BRANCH_BODY`
- `COLLECTION_PREDICATE_BODY`

This metadata now appears in:

- `rewriteFacts.dynamicTemplate.capabilityProfile.surfaceContract`
- review-only patch-selection `rewriteMaterialization`
- review-only patch-selection `templateRewriteOps`

The important point is not patchability.

The important point is that the pipeline can describe the missing substrate without pretending the feature already exists.

### 3. Choose-local substrate is now real

The project now has a real choose-local execution path for supported synthetic cases:

- `dynamic_surface_locator` can locate a target choose branch
- `template_materializer` can materialize `replace_choose_branch_body`
- `patching_templates` can build a local choose-body patch
- `patch_replay` can replay and verify the local choose-body rewrite

This means the dynamic substrate question is no longer hypothetical.

It is implemented for the narrow choose-local op.

## What The Choose Prototype Proved

The choose prototype did produce a real safe-baseline family for localized choose shapes:

- `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`

But it did not promote the real sample-project sentinel.

The important finding is narrower and more useful:

- choose-local substrate exists
- synthetic branch-local choose cleanup can now be represented honestly
- the real `findUsersByKeyword` statement still does not qualify for that family

The blocker is not missing patch substrate anymore.

The blocker is also no longer missing branch-local identity:

- scan and catalog now provide `dynamicRenderIdentity`
- optimize prompt and cassette replay consume that identity

The remaining blocker is that the provider still emits only low-value or speculative candidates for the sample-project sentinel under that richer context.

## Why The Real Sentinel Still Fails

Promotion now fails for a more specific reason:

- `findUsersByKeyword` is structurally a supported choose-guarded filter
- but its `original_sql` represents a flattened OR over choose branches
- `locate_choose_branch_surface(...)` cannot bind that SQL to one concrete branch

That means the system would be lying if it promoted this statement directly to:

- `DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP`

The family is real.

The real sentinel simply is not a member of that family under the current scan/original-sql contract.

## Replay Evidence

Fresh replay checks remained stable:

- `generalization-batch9`
- `generalization-batch13`

Observed truth now is:

- `demo.user.advanced.findUsersByKeyword`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.order.harness.findOrdersByUserIdsAndStatus`
  - `MANUAL_REVIEW / NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`

Guardrails did not widen.

No patch files were emitted.

A final narrow provider-side contract trial was also completed:

- optimize prompt now carries an explicit choose-local surface contract
- cassette replay fingerprinting now includes that contract
- targeted reseed still produced only speculative or low-value candidates

Fresh replay after that trial:

- `generalization-batch9` -> `run_0bba13603075`
- `generalization-batch13` -> `run_5662aef54d87`

Observed provider output under the stricter contract still stayed in the low-value lane:

- `INDEX_SEEK`
- `PREDICATE_SIMPLIFICATION`
- `PREDICATE_REDUCTION`

## Final Recommendation

Do not keep pushing this lane inside the current engineering program.

Treat this as a successful capability split:

- choose-local substrate is now real
- a narrow choose-local family is now real
- the sample-project sentinel is still correctly deferred because provider output quality remains below the bar for branch-local safe-baseline promotion

If product later wants to promote the real sentinel, that becomes a different investment:

- a provider-quality program that can reliably emit non-speculative branch-local rewrites
- or a new dynamic semantic model for flattened choose envelopes

That next stage is now captured in:

- `docs/superpowers/specs/2026-04-09-choose-flattened-envelope-contract-design.md`
- `docs/superpowers/plans/2026-04-09-choose-flattened-envelope-contract-program.md`

Until then:

- `CHOOSE_BRANCH_BODY` remains a valid promoted family only for local-surface choose shapes
- `demo.user.advanced.findUsersByKeyword` remains deferred
- `COLLECTION_PREDICATE_BODY` remains deferred
- no more prompt tweaking or exploratory choose batches should happen on this branch
