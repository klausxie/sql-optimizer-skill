# Unsupported-Strategy Boundary Program

## Goal

Execute the next post-semantic stage by freezing the remaining unsupported-strategy tails as explicit current non-goals.

This stage should answer one bounded product question:

> are the current unsupported-strategy blockers already the final truth, and if so, can we freeze them cleanly without widening any neighboring boundary?

## Design Reference

- [2026-04-09-unsupported-strategy-boundary-design.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-unsupported-strategy-boundary-design.md)

## Primary Sentinels

- `demo.test.complex.existsSubquery`
- `demo.test.complex.inSubquery`
- `demo.test.complex.leftJoinWithNull`

Current truths:

- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`

## Guardrail Sentinels

- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.test.complex.includeNested`
- `demo.user.findUsers`
- `demo.test.complex.staticSimpleSelect`

These must remain in their own lanes while unsupported-strategy truth is frozen.

## Scope Boundaries

Allowed scope:

- blocker inventory cleanup
- reason-code clarification only if it improves final truth
- replay-based evidence refresh
- explicit freeze documentation

Out of scope:

- any new capability work
- join rewrite support
- exists/in-subquery support
- semantic comparator relaxation
- low-value cleanup

## Task 1: Freeze Unsupported Truth

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

Work:

- add explicit primary and guardrail sentinel sets for this stage
- lock current truths for the three unsupported statements
- ensure semantic/validate/low-value guardrails remain outside the unsupported lane

**Success standard:** later cleanup cannot accidentally widen or relabel neighboring lanes.

## Task 2: Refresh Replay Evidence

**Files:**

- replay artifacts only

Work:

- rerun the batches that contain the primary unsupported statements and guardrails
- confirm current reason codes still match the intended unsupported subtype

**Success standard:** fresh replay still shows the same three explicit unsupported tails.

## Task 3: Freeze Review

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-review.md`

Work:

- record the fresh replay verdict
- state explicitly that this lane is frozen for current scope
- point the next stage at low-value cleanup or comparator-strengthening, not unsupported-strategy capability work

**Success standard:** this lane is closed with an explicit product decision, not left as an implied backlog.

## Final Verdict

Program complete.

Outcome:

- unsupported `EXISTS`, `IN` subquery rewrite, and join-type change tails remain explicit current non-goals
- semantic, validate, and low-value guardrails remain in their own lanes
- no patchability was widened

Supporting evidence:

- [2026-04-09-unsupported-strategy-boundary-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-unsupported-strategy-boundary-review.md)
