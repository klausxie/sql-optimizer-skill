# Generalization Batch12 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch12` as a candidate-selection program centered on the truthful lanes visible in the fresh replay baseline:

1. unsupported-strategy guardrail for `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
2. low-value candidate guardrail for `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
3. semantic guardrail for `SEMANTIC_PREDICATE_CHANGED`

This program is successful if it either promotes `staticSimpleSelect` through an already-supported path or leaves every target blocked with a cleaner, more stable reason. It is not successful if it broadens `EXISTS`, JOIN/null, or pagination semantics to manufacture green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch12`: `run_a344702c1794`

Current truth:
- `demo.test.complex.staticSimpleSelect` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK`
- `demo.test.complex.inSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE`
- `demo.test.complex.leftJoinWithNull` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

## Task 1: Freeze the Batch12 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch12-intake.md`

- [x] Add `generalization-batch12` as a formal runnable batch.
- [x] Freeze the five-statement scope exactly.
- [x] Keep this step observational only.

**Success standard:** `batch12` can be refreshed and summarized without ad-hoc SQL selection.

## Task 2: Lane A — Unsupported-Strategy Guardrails

**Targets:**
- `demo.test.complex.existsSubquery`
- `demo.test.complex.inSubquery`
- `demo.test.complex.leftJoinWithNull`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Reconfirm that all three remain truthful unsupported-strategy blockers.
- [ ] Only reclassify if optimize/validate already contains stronger evidence for a narrower blocker.
- [ ] Do not invent a new patch family or silently downgrade unsupported strategies into low-value candidates.

**Success standard:** all three stay blocked for the same candidate-selection class of reason, or move to an even more honest blocker without widening semantics or patch families.

## Task 3: Lane B — Low-Value Candidate Guardrail

**Target:**
- `demo.test.complex.staticSimpleSelect`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Reconfirm that `staticSimpleSelect` is still a truthful low-value blocker.
- [ ] Only promote it if an already-supported path truly exists.

**Success standard:** `staticSimpleSelect` either stays low-value with a stable reason or moves to an already-supported path without collateral promotion.

## Task 4: Lane C — Semantic Canary

**Target:**
- `demo.order.harness.listOrdersWithUsersPaged`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Keep `listOrdersWithUsersPaged` blocked unless an evidence-backed comparison fix exists.
- [ ] Do not weaken pagination or dynamic-filter predicate semantics for convenience.

**Success standard:** the semantic canary stays blocked for the same semantic class of reason, or moves to an even more honest blocker without semantic weakening.

## Task 5: Fresh Rerun and Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch12-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch13-intake.md`

- [ ] Fresh rerun `generalization-batch12`.
- [ ] Re-run `generalization_summary.py` for `batch1..12`.
- [ ] Only create `batch13` intake after the fresh rerun confirms the next truthful dominant lane.
