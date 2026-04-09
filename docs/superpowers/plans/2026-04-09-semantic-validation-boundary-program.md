# Semantic/Validation Boundary Program

## Goal

Execute the next post-safe-baseline stage by determining whether the remaining semantic and validation blockers are true product boundaries or comparator/validator-policy weaknesses.

This stage should answer one bounded product question:

> should the current semantic/validation tails be frozen as explicit boundaries, or narrowed into more honest blocker meanings without widening patchability?

## Design Reference

- [2026-04-09-semantic-validation-boundary-design.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-semantic-validation-boundary-design.md)

## Why This Program Exists

The safe-baseline stage is complete:

- choose-aware re-deferred
- collection-predicate deferred
- fragment/include frozen

That means the highest-value remaining uncertainty is no longer a missing safe path.

It is the semantic/validation surface:

- `SEMANTIC_PREDICATE_CHANGED`
- `VALIDATE_SEMANTIC_ERROR`
- `VALIDATE_STATUS_NOT_PASS`

## Primary Sentinels

- `demo.order.harness.listOrdersWithUsersPaged`
  - `MANUAL_REVIEW / SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.includeNested`
  - `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.user.findUsers`
  - `MANUAL_REVIEW / VALIDATE_STATUS_NOT_PASS`

## Guardrail Sentinels

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.fragmentMultiplePlaces`
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.existsSubquery`

These statements must remain blocked while the semantic/validation lane is reviewed.

## Scope Boundaries

Allowed scope:

- comparator result clarification
- validator blocker clarification
- replay-based evidence gathering
- tighter blocker naming when it improves product truth

Out of scope:

- new patch families
- semantic rule loosening that changes delivery outcome
- join/exists promotion
- choose-aware reopening
- collection or fragment capability reopening

## Task 1: Freeze Current Semantic/Validation Truth

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

Work:

- lock the primary and guardrail sentinels for this stage
- keep current truths explicit:
  - `listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
  - `includeNested` -> `VALIDATE_SEMANTIC_ERROR`
  - `findUsers` -> `VALIDATE_STATUS_NOT_PASS`

**Success standard:** implementation cannot accidentally widen semantic or validator canaries while this stage is running.

## Task 2: Clarify Semantic Predicate Lane

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

Work:

- determine whether `SEMANTIC_PREDICATE_CHANGED` on `listOrdersWithUsersPaged` is:
  - a real semantic boundary
  - or a comparator artifact
- only narrow the blocker if there is exact evidence
- do not allow the statement to become auto-patchable as part of this stage

**Success standard:** the semantic canary ends the stage with a more defensible blocker truth, not a weaker guard.

## Task 3: Clarify Validate Semantic Lane

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/harness/fixture/`

Work:

- determine whether `includeNested` is a stable nested-include semantic boundary
- split the current blocker only if the split reflects a real, reusable validator truth
- do not collapse it into generic semantic or candidate buckets

**Success standard:** `includeNested` ends the stage with either the same blocker or a more honest subtype, but not a softened delivery outcome.

## Task 4: Freeze Validate Status Hard Boundaries

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/`

Work:

- confirm `findUsers` and `fragmentMultiplePlaces` remain hard validator boundaries
- if useful, give them clearer final meanings
- do not route them into semantic or candidate lanes

**Success standard:** risky substitution and fragment-misplacement statements stay explicitly blocked as validator boundaries.

## Task 5: Fresh Replay Review

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-review.md`

Work:

- rerun primary and guardrail sentinels in replay
- verify:
  - ready sentinels remain ready
  - semantic/validation canaries remain blocked
  - choose/collection/fragment lanes remain blocked
  - unsupported-strategy guardrails do not drift
- record whether semantic/validation truth narrowed or simply stayed frozen

**Success standard:** the stage ends with a stable yes/no verdict about semantic/validation ambiguity, not another exploratory backlog note.

## Exit Criteria

This program is complete when:

1. semantic and validation sentinels have explicit final truth
2. no patchable boundary was widened accidentally
3. guardrail lanes remain blocked
4. the project is ready to choose between:
   - boundary freeze
   - unsupported-strategy cleanup
   - or a future comparator-strengthening stage

## Final Verdict

Program complete.

Outcome:

- `listOrdersWithUsersPaged` is an honest semantic boundary, not a generic comparator mystery
- `includeNested` is an honest validate/semantic boundary rooted in row-count evaluation failure
- `findUsers` remains an explicit validator boundary under `VALIDATE_SECURITY_DOLLAR_SUBSTITUTION`
- no semantic or validation lane was widened into auto patch

Supporting evidence:

- [2026-04-09-semantic-validation-boundary-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-semantic-validation-boundary-review.md)
