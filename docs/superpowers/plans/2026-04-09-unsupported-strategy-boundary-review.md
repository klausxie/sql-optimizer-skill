# Unsupported-Strategy Boundary Review

## Verdict

The unsupported-strategy stage is complete.

This lane should be treated as explicitly frozen for current product scope.

The remaining unsupported tails are already honest:

- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

No additional capability work is justified in this stage.

## What The Stage Confirmed

### Primary unsupported tails stayed stable

Fresh replay evidence:

- [run_16f54964ecc2](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_16f54964ecc2)
  - `demo.test.complex.existsSubquery`
    - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
  - `demo.test.complex.inSubquery`
    - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
  - `demo.test.complex.leftJoinWithNull`
    - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

These three statements did not drift back into:

- generic `NO_PATCHABLE_CANDIDATE_SELECTED`
- semantic blocker lanes
- validate blocker lanes

### Guardrails stayed in their own lanes

Fresh replay evidence:

- [run_51e1023139f3](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_51e1023139f3)
  - `demo.order.harness.listOrdersWithUsersPaged`
    - `MANUAL_REVIEW / SEMANTIC_PREDICATE_CONJUNCT_REMOVED`
  - `demo.test.complex.includeNested`
    - `MANUAL_REVIEW / VALIDATE_SEMANTIC_ROW_COUNT_ERROR`
- [run_4ef12b70f1a0](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_4ef12b70f1a0)
  - `demo.user.findUsers`
    - `MANUAL_REVIEW / VALIDATE_SECURITY_DOLLAR_SUBSTITUTION`
- [run_b6b982ecccc4](/tmp/sqlopt-post-batch7/tests/fixtures/projects/sample_project/runs/run_b6b982ecccc4)
  - `demo.test.complex.staticSimpleSelect`
    - `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT`

This is the important outcome of the stage:

- unsupported tails stayed unsupported
- semantic stayed semantic
- validate stayed validate
- low-value stayed low-value

## Why This Lane Is Frozen

Each primary unsupported tail would require a different new capability family:

- correlated `EXISTS` null-check handling
- `IN` subquery rewrite support
- join-type change support

That is not one missing safe path. It is three separate product decisions.

Treating them as “cleanup candidates” would blur the project boundary and re-open exploratory capability work that the current roadmap is explicitly avoiding.

## Exit Decision

The unsupported-strategy stage ends with:

- `PROMOTE = no`
- `FREEZE = yes`
- `NEW PATCH FAMILY = no`
- `READY REGRESSIONS = 0`
- `BLOCKED BOUNDARY REGRESSIONS = 0`

The next stage should move to either:

1. low-value/no-op boundary cleanup
2. comparator-strengthening
3. final project boundary freeze and delivery summary
