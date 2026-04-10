# Supported Capability Matrix

## Purpose

This matrix is the product-facing expression of the current optimizer boundary.

It answers a user-visible question:

> what does the optimizer support now, what is intentionally blocked, and why?

It is not a historical catalog of every explored statement.

It is the supported-scope surface derived from the completed boundary programs.

## Category Definitions

### `SUPPORTED`

Current product scope that can truthfully reach `AUTO_PATCHABLE` under the existing architecture.

This is the strongest "yes" category.

### `DEFERRED_CAPABILITY`

Not supported now, but explicitly left open for a future funded capability track.

These are not bugs and should not be presented as accidental failures.

### `FROZEN_NON_GOAL`

Explicitly out of current scope.

These lanes should remain blocked unless product intentionally reopens them.

### `SEMANTIC_BOUNDARY`

Blocked because the candidate changes semantics or the project cannot honestly prove semantic equivalence today.

### `VALIDATE_SECURITY_BOUNDARY`

Blocked because validation or security rules reject the candidate, independent of patch substrate.

### `PROVIDER_LIMITED`

Engineering substrate is ready, but the current provider/model path does not emit promotable candidates.

This is a distinct category because the root cause is no longer in scan, replay, or patching.

## Current Matrix

| Category | Meaning | Representative Sentinels | Current Product Message |
|---|---|---|---|
| `SUPPORTED` | safe and patchable under current contracts | `demo.user.countUser`, `demo.test.complex.fromClauseSubquery`, `demo.test.complex.wrapperCount` | supported and auto-patchable |
| `DEFERRED_CAPABILITY` | real future capability, not funded now | `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE` | deferred capability |
| `FROZEN_NON_GOAL` | intentionally out of scope | `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`, `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`, `NO_SAFE_BASELINE_GROUP_BY`, `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_*`, `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT` | unsupported in current scope |
| `SEMANTIC_BOUNDARY` | candidate changes semantics or cannot be proven equivalent | `SEMANTIC_PREDICATE_CONJUNCT_REMOVED` | blocked by semantic safety |
| `VALIDATE_SECURITY_BOUNDARY` | validator or security policy blocks progress | `VALIDATE_SEMANTIC_ROW_COUNT_ERROR`, `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION` | blocked by validation/security |
| `PROVIDER_LIMITED` | provider fails to emit promotable candidate despite ready substrate | `demo.user.advanced.findUsersByKeyword` | blocked by current provider quality |

## Detailed Boundary Assignments

### Supported Today

These represent the delivered optimizer core:

- wrapper / redundant-wrapper cleanup on stable static shapes
- static include-only cleanup where convergence and patch family already match
- selected alias / distinct / wrapper family paths proven by replay

Representative sentinels:

- `demo.user.countUser`
- `demo.test.complex.fromClauseSubquery`
- `demo.test.complex.wrapperCount`

### Deferred Future Capability

These are the only boundaries that should still be described as future capability opportunities:

- `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- provider-limited choose-local support

Important distinction:

- collection remains `DEFERRED_CAPABILITY`
- choose-local now belongs under `PROVIDER_LIMITED`, not under generic safe-baseline uncertainty

### Frozen Non-Goals

These are current product boundaries:

- `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `NO_SAFE_BASELINE_GROUP_BY`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`
- `NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`
- generic `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` outcomes where no funded future lane exists

### Semantic Boundaries

These are not capability gaps.

They are integrity boundaries:

- `SEMANTIC_PREDICATE_CONJUNCT_REMOVED`
- other stable `SEMANTIC_*` conflict reasons that indicate predicate or equivalence drift

Representative sentinel:

- `demo.order.harness.listOrdersWithUsersPaged`

### Validate / Security Boundaries

These represent validator truth, not candidate-selection truth:

- `VALIDATE_SEMANTIC_ROW_COUNT_ERROR`
- `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION`

Representative sentinels:

- `demo.test.complex.includeNested`
- `demo.user.findUsers`

### Provider-Limited Boundary

This is currently a one-lane category:

- `demo.user.advanced.findUsersByKeyword`

Status:

- dynamic choose-local substrate is ready
- branch identity is available
- prompt contract was tightened
- provider-quality research still produced `0% branch_local_valid`

Therefore the truthful product category is:

- supported by engineering substrate
- not supported by current provider quality

## Product Messaging Rules

The matrix should drive messaging that is:

- honest
- compact
- stable across releases

Recommended phrasing:

- `SUPPORTED` -> "supported"
- `DEFERRED_CAPABILITY` -> "not supported yet"
- `FROZEN_NON_GOAL` -> "not supported in current scope"
- `SEMANTIC_BOUNDARY` -> "blocked by semantic safety"
- `VALIDATE_SECURITY_BOUNDARY` -> "blocked by validation/security"
- `PROVIDER_LIMITED` -> "blocked by current provider quality"

## Source Of Truth

This matrix is derived from:

- [2026-04-09-project-boundary-delivery-summary.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-project-boundary-delivery-summary.md)
- [2026-04-09-safe-baseline-program-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)
- [2026-04-09-semantic-validation-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-review.md)
- [2026-04-09-unsupported-strategy-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-review.md)
- [2026-04-09-low-value-boundary-review.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-low-value-boundary-review.md)
- [2026-04-10-provider-strategy-decision.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-10-provider-strategy-decision.md)

## Expected Outcome

After this matrix is adopted, the product should no longer rely on internal planning vocabulary alone.

It should have a stable supported-scope statement that can be surfaced in docs, reports, and release notes.
