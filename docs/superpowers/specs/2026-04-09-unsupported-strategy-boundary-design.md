# Unsupported-Strategy Boundary Design

## Goal

Define the next post-semantic stage around one bounded product question:

> are the remaining unsupported-strategy tails final non-goals that should be frozen explicitly, or is any of them still mislabeled and worth narrowing further?

This stage is not a capability program.

It is a boundary-cleanup program for statements that are already clearly out of scope for the current patch system.

## Why This Stage Comes Next

The project has already completed:

- safe-baseline design and subtype disposition
- choose-aware review and re-defer
- collection-predicate review and defer
- fragment/include review and freeze
- semantic/validation clarification

That means the next highest-value cleanup is the unsupported rewrite lane:

- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

These are already honest blockers, but they still deserve one explicit stage so the product boundary is documented instead of implied.

## Primary Sentinels

- `demo.test.complex.existsSubquery`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `demo.test.complex.inSubquery`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `demo.test.complex.leftJoinWithNull`
  - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

## Guardrail Sentinels

- `demo.order.harness.listOrdersWithUsersPaged`
  - semantic boundary; must stay semantic, not drift into unsupported lane
- `demo.test.complex.includeNested`
  - validate boundary; must stay validate, not drift into unsupported lane
- `demo.user.findUsers`
  - validator/security boundary; must remain hard-blocked
- `demo.test.complex.staticSimpleSelect`
  - low-value/no-op canary; must remain outside unsupported strategy

## Design Decision

Use a **boundary-freeze program**, not a capability program.

This stage should:

- verify these three unsupported tails are stable
- ensure they do not drift into semantic or low-value buckets
- freeze them as explicit current non-goals

This stage should not:

- create new patch families
- reopen join/exists/in-subquery capability work
- loosen semantic or validator boundaries
- attempt green movement

## Recommended Output

At the end of this stage:

- the three unsupported subtypes are explicitly frozen
- semantic/validate/low-value guardrails remain intact
- the project can move on to low-value cleanup or comparator-strengthening without ambiguity
