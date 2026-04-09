# Semantic/Validation Boundary Review

## Verdict

The semantic/validation stage is complete.

It did not create new patchable capability, but it converted the primary semantic/validation canaries from broad buckets into explicit product truth.

## What Changed

### 1. Semantic predicate drift is now more explicit

`demo.order.harness.listOrdersWithUsersPaged` no longer sits in the generic `SEMANTIC_PREDICATE_CHANGED` lane.

It now lands in:

- `SEMANTIC_PREDICATE_CONJUNCT_REMOVED`

This is more honest because the selected candidate does not merely “change” a predicate. It removes one top-level conjunct entirely:

- before:
  - `(u.name ilike ... or u.email ilike ...) and o.status = #{status}`
- after:
  - `o.status = #{status}`

The DB fingerprint remains exact only because the compared result set is empty. That is not a reason to promote it; it is a reason to keep the blocker explicit.

### 2. Nested include validation is now more explicit

`demo.test.complex.includeNested` no longer collapses into a generic `VALIDATE_SEMANTIC_ERROR`.

It now lands in:

- `VALIDATE_SEMANTIC_ROW_COUNT_ERROR`

This is more honest because the underlying acceptance evidence is:

- semantic structure checks pass
- row-count evidence fails
- fingerprint evidence is skipped

So the lane is not “semantic changed” in a generic sense. It is a validator boundary caused by missing reliable row-count confirmation.

### 3. Risky substitution remains an explicit validator boundary

`demo.user.findUsers` remains:

- `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION`

This was already the correct truth, and the fresh replay review confirms it should remain frozen.

## Fresh Replay Evidence

### Primary sentinels

- [run_4ef12b70f1a0](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_4ef12b70f1a0)
  - `demo.user.findUsers` -> `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION`
- [run_51e1023139f3](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_51e1023139f3)
  - `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CONJUNCT_REMOVED`
  - `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ROW_COUNT_ERROR`

### Guardrails

- [run_b6b982ecccc4](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_b6b982ecccc4)
  - `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ROW_COUNT_ERROR`
  - `demo.test.complex.fragmentInJoin` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- [run_16f54964ecc2](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_16f54964ecc2)
  - `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
  - `demo.test.complex.inSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
  - `demo.test.complex.leftJoinWithNull` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

No guardrail widened into `AUTO_PATCHABLE`.

## Why The Stage Ends Here

This stage answered the important product question:

- `listOrdersWithUsersPaged` is a real semantic boundary, not a comparator bug
- `includeNested` is a real validate-row-count boundary, not a generic semantic bucket
- `findUsers` remains a hard validator/security boundary

That is enough to stop exploratory semantic clarification.

What remains after this stage is no longer ambiguous semantic truth. It is product choice:

- freeze these boundaries explicitly
- or later invest in a comparator/validator-strengthening track

## Exit Decision

The semantic/validation stage ends with:

- `PROMOTE = no`
- `BOUNDARY CLARIFICATION = yes`
- `NEW PATCH FAMILY = no`
- `READY REGRESSIONS = 0`
- `BLOCKED BOUNDARY REGRESSIONS = 0`

The next stage should not reopen safe-baseline or batch exploration. It should choose between:

1. unsupported-strategy boundary cleanup
2. low-value/no-op boundary cleanup
3. a future comparator-strengthening program
