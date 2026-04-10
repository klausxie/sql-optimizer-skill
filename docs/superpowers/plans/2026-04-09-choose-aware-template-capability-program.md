# Choose-Aware Template Capability Program

## Goal

Execute the next capability-driven stage after the safe-baseline review by determining whether a narrow choose-aware template-preserving path is viable.

This program should not reopen generic family exploration and should not introduce broad `CHOOSE` support.

Reference design:

- [2026-04-09-choose-aware-template-capability-design.md](/tmp/sqlopt-post-batch7/docs/superpowers/specs/2026-04-09-choose-aware-template-capability-design.md)

## Primary Sentinel

- `demo.user.advanced.findUsersByKeyword`

## Guardrail Sentinels

- `demo.test.complex.chooseBasic`
- `demo.test.complex.chooseMultipleWhen`
- `demo.test.complex.chooseWithLimit`
- `demo.test.complex.selectWithFragmentChoose`
- `demo.order.harness.listOrdersWithUsersPaged`

## Task 1: Freeze Current Choose Truth

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`

Work:

- lock today’s choose-aware sentinel truth
- explicitly guard that unsupported choose sentinels stay blocked

**Success standard:** implementation cannot accidentally broaden choose support while the capability is being explored.

## Task 2: Add Choose-Aware Capability Profile

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/rewrite_facts.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_rewrite_facts.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`

Work:

- add an explicit choose-aware capability/profile marker
- distinguish “supported choose shape but no branch-safe rewrite exists” from generic unsafe statement rewrite

**Success standard:** choose-aware capability is a first-class, testable concept in `rewrite_facts`, not just an inferred blocker subtype.

## Task 3: Prototype One Branch-Local Safe Path

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/`

Work:

- identify whether any branch-local, template-preserving choose rewrite can be proven safe
- if one exists, implement only that path
- if none exists, do not broaden heuristics; mark the lane as still deferred

**Success standard:** one branch-local safe path is either proven or ruled out with code-level evidence.

## Task 4: Patch Surface And Guarded Delivery

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/patch_generate.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_utils.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/patch_safety.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/patch/`

Work:

- only if Task 3 proves a real safe path exists
- add the minimal template patch surface required to preserve `<choose>` branches
- block delivery if patch generation would flatten or structurally widen the template

**Success standard:** any choose-aware delivery path remains template-preserving.

## Task 5: Fresh Replay Review

**Files:**

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-choose-aware-template-capability-program.md`
- `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-choose-aware-template-capability-review.md`

Work:

- rerun the choose sentinel set in replay
- verify:
  - no ready regressions
  - no semantic canary regressions
  - non-goal choose statements remain blocked
- record whether the primary sentinel gained a safe path or remained deferred

**Success standard:** the capability stage ends with a clear yes/no verdict, not another vague “almost there.”

## Non-Goals

This program must not:

- auto-open `batch14`
- support pagination-changing choose rewrites
- support fragment-driven choose branches
- flatten `<choose>` into one predicate string for patch delivery
- loosen `SEMANTIC_PREDICATE_CHANGED` boundaries

## Exit Criteria

This program is complete when:

1. choose-aware capability is either promoted narrowly or re-deferred with stronger code evidence
2. unsupported choose shapes remain blocked
3. fresh replay review confirms no regressions
4. the next stage is named by capability, not by another exploratory batch number

## Outcome

Status: complete, re-deferred.

What was proven:

- the primary sentinel `demo.user.advanced.findUsersByKeyword` is now represented as an explicit choose-aware review-only capability lane instead of generic dynamic unsafe rewrite
- current code has no branch-local consumer for `patchSurface = CHOOSE_BRANCH_BODY`
- no existing safe-baseline family can accept the primary sentinel without widening support beyond the approved boundary

What was not done:

- no new choose patch family was introduced
- no template-flattening patch path was added
- Task 4 was intentionally skipped because Task 3 did not prove a safe path

Fresh replay review used:

- `generalization-batch5` -> `run_7eb066571c1d`
- `generalization-batch13` -> `run_f862952bca4c`

Final verdict:

- `demo.user.advanced.findUsersByKeyword` remains `MANUAL_REVIEW / NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.chooseBasic` remains `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseMultipleWhen` remains `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.chooseWithLimit` remains `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.selectWithFragmentChoose` remains `MANUAL_REVIEW / VALIDATE_SEMANTIC_ERROR`
- `demo.order.harness.listOrdersWithUsersPaged` remains `MANUAL_REVIEW / SEMANTIC_PREDICATE_CHANGED`

Next stage:

- do not open `batch14`
- move to a new capability program only if there is a deliberate product decision to support choose-aware branch-local template edits with a dedicated safe-baseline family
