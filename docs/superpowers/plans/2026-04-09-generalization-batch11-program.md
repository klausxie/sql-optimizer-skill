# Generalization Batch11 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch11` as a mixed blocker program centered on the truthful lanes visible in the fresh replay baseline:

1. candidate-selection guardrail for `NO_PATCHABLE_CANDIDATE_*`
2. semantic guardrail for `SEMANTIC_PREDICATE_CHANGED`
3. validate/semantic guardrail for `VALIDATE_SEMANTIC_ERROR`
4. safe-baseline guardrail for `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`

This program is successful if it either promotes `staticSimpleSelect` through an already-supported path or leaves every target blocked with a cleaner, more stable reason. It is not successful if it broadens `EXISTS` / pagination semantics or weakens include boundaries to manufacture green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch11`: `run_2fdcb5d7df7b`

Current truth:
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.existsSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
- `demo.test.complex.fragmentInJoin` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.test.complex.staticSimpleSelect` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`

## Task 1: Freeze the Batch11 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch11-intake.md`

- [x] Add `generalization-batch11` as a formal runnable batch.
- [x] Freeze the five-statement scope exactly.
- [x] Keep this step observational only.

**Success standard:** `batch11` can be refreshed and summarized without ad-hoc SQL selection.

## Task 2: Lane A — Semantic and Unsupported-Strategy Guardrails

**Targets:**
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.test.complex.existsSubquery`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [x] Reconfirm that `listOrdersWithUsersPaged` remains a truthful semantic blocker.
- [x] Relax comparison for `existsSubquery` only where equivalence is already structurally justified and evidence-backed.
- [ ] Do not weaken pagination or `EXISTS` semantics for convenience.

**Success standard:** `listOrdersWithUsersPaged` stays blocked for the same semantic class of reason, while `existsSubquery` either stays semantic or moves to an even more honest candidate-selection blocker without semantic weakening.

## Task 3: Lane B — Validate/Semantic Include Guardrail

**Target:**
- `demo.test.complex.includeNested`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] Reconfirm that `VALIDATE_SEMANTIC_ERROR` is a truthful blocker for nested include shapes.
- [ ] Do not turn nested include validation failures into candidate-selection work.

**Success standard:** `includeNested` remains blocked for the same truthful class of reason, or moves to an even more honest blocker without broad include recovery.

## Task 4: Lane C — Boundary Canaries

**Targets:**
- `demo.test.complex.fragmentInJoin`
- `demo.test.complex.staticSimpleSelect`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Keep `fragmentInJoin` in the safe-baseline lane unless an already-supported multi-fragment include path truly exists.
- [ ] Keep `staticSimpleSelect` in the low-value candidate lane unless an already-supported path truly exists.
- [ ] Do not let semantic cleanup blur either boundary.

**Success standard:** both targets remain blocked for the same truthful class of reason, or move to an even more honest blocker without collateral promotion.

## Task 5: Fresh Rerun and Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch11-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch12-intake.md`

- [ ] Fresh rerun `generalization-batch11`.
- [ ] Re-run `generalization_summary.py` for `batch1..11`.
- [ ] Only create `batch12` intake after the fresh rerun confirms the next truthful dominant lane.
