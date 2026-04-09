# Fragment/Include Preservation Program

## Goal

Execute the next capability stage by determining whether any narrow, template-preserving path exists for fragment/include preservation.

This stage should answer one bounded product question:

> can any multi-fragment include lane be promoted safely, or should the current fragment/include surface remain an explicit frozen boundary?

## Why This Program Exists

The current roadmap is already narrowed:

- choose-aware was re-deferred
- collection-predicate was re-deferred
- `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE` remains the next major frozen subtype with repeated real sentinels

The safe-baseline decision table already marked this lane as `FREEZE`, but that decision still deserves one focused capability review before the project moves on completely.

Reference decisions:

- [2026-04-09-safe-baseline-decision-table.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-safe-baseline-decision-table.md)
- [2026-04-09-safe-baseline-program-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-safe-baseline-program-review.md)
- [2026-04-09-collection-predicate-capability-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-collection-predicate-capability-review.md)

## Primary Sentinel

- `demo.test.complex.multiFragmentLevel1`

Current truth:

- `MANUAL_REVIEW / NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`

This statement should decide whether any fragment/include-preserving path is real.

## Guardrail Sentinels

- `demo.test.complex.includeNested`
  - semantic-risk include canary; must not be widened accidentally
- `demo.test.complex.fragmentInJoin`
  - join-adjacent fragment canary; must not be promoted by simple include preservation
- `demo.test.complex.includeWithWhere`
  - include-plus-filter canary; must not be mistaken for a safe static include lane
- `demo.order.harness.listOrdersWithUsersPaged`
  - semantic canary; must remain blocked if predicate semantics still drift
- `demo.user.advanced.findUsersByKeyword`
  - choose-aware deferred lane; must not be “fixed by accident”

## Program Question

Can we support a narrow fragment/include capability that:

- preserves multiple include refs as include refs
- does not inline or flatten dynamic fragments into executable SQL
- keeps patch edits local to a stable statement body or fragment boundary
- does not relax semantic gates or join/order/pagination boundaries

If yes, promote only that narrow path.

If no, keep the lane frozen with stronger evidence.

## Scope Boundaries

Allowed scope:

- multiple `<include>` refs inside a single statement body
- template-preserving edits only
- replay-based verification on existing sentinels

Out of scope:

- broad fragment materialization
- nested include expansion across dynamic subtrees
- choose-aware editing
- collection-predicate handling
- join/pagination semantic relaxation
- new exploratory `batch14`

## Task 1: Freeze Current Fragment/Include Truth

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

Work:

- lock the primary sentinel and guardrail sentinel set for this capability stage
- ensure current truth stays explicit:
  - `multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `includeNested` remains semantic-risk

**Success standard:** implementation cannot accidentally widen fragment/include canaries while the lane is being investigated.

## Task 2: Add Fragment/Include Capability Profile

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/rewrite_facts.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_rewrite_facts.py`

Work:

- determine whether multi-fragment include statements deserve a distinct review-only capability profile
- distinguish:
  - multi-fragment include preservation candidates
  - from generic static include or generic dynamic-template lanes

**Success standard:** the lane is a first-class reviewable concept, not just another generic blocker.

## Task 3: Probe For One Narrow Safe Path

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/`

Work:

- determine whether there is one narrow path that:
  - preserves multiple include refs
  - keeps edits local to a stable template envelope
  - is reusable beyond a single statement
- if yes, implement only that one path
- if no, do not widen heuristics; explicitly confirm the frozen boundary

**Success standard:** one real path is either proven with code/tests or ruled out with code/tests.

## Task 4: Patch Surface Guard

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_utils.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_safety.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/patch_generate.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/patch/`

Work:

- only if Task 3 proves a real safe path exists
- add the minimum patch surface needed to preserve include refs and statement envelope
- block delivery if patch generation would inline fragments, flatten dynamic structure, or widen scope

**Success standard:** any promoted path stays template-preserving end-to-end.

## Task 5: Fresh Replay Review

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-fragment-include-preservation-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-fragment-include-preservation-review.md`

Work:

- rerun the primary sentinel and guardrails in replay
- verify:
  - no ready regressions
  - semantic canaries remain honest
  - choose and collection deferred lanes remain blocked
- record whether fragment/include preservation gained a safe path or stayed frozen

**Success standard:** the stage ends with a yes/no verdict, not another vague backlog entry.

## Exit Criteria

This program is complete when:

1. fragment/include preservation is either promoted narrowly or kept frozen with stronger evidence
2. semantic and deferred guardrails remain blocked
3. replay review confirms no regressions in choose, collection, or pagination/join canaries
4. the next stage remains capability-driven, not exploratory batch growth

## Final Verdict

Program complete.

Outcome:

- `MULTI_FRAGMENT_INCLUDE` is now a first-class review-only lane
- no latent safe-baseline recovery path exists in the current system
- no patch-surface work is justified
- the lane remains `FREEZE`, not `PROMOTE`

Supporting evidence:

- fresh replay truth:
  - `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `demo.test.complex.fragmentInJoin` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `demo.test.complex.includeWithWhere` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
  - `demo.test.complex.includeNested` stays `VALIDATE_SEMANTIC_ERROR`
  - `demo.order.harness.listOrdersWithUsersPaged` stays `SEMANTIC_PREDICATE_CHANGED`
- proposal diagnostics for all three primary fragment/include sentinels remain:
  - `degradationKind=EMPTY_CANDIDATES`
  - `recoveryReason=NO_SAFE_BASELINE_SHAPE_MATCH`
  - `recoveredCandidateCount=0`
- convergence now blocks `MULTI_FRAGMENT_INCLUDE` even if a selected candidate and patch family hint appear, so the lane cannot be auto-promoted accidentally

Reference review:

- [2026-04-09-fragment-include-preservation-review.md](/tmp/sqlopt-post-batch7/docs/superpowers/plans/2026-04-09-fragment-include-preservation-review.md)
