# Generalization Batch10 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch10` as a mixed blocker program centered on the truthful lanes visible in the fresh replay baseline:

1. `NO_SAFE_BASELINE_RECOVERY`
2. semantic guardrail for `SEMANTIC_PREDICATE_CHANGED`
3. unsupported-strategy guardrail for `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
4. safe-baseline guardrail for `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`

This program is successful if it either promotes `staticGroupBy` through an already-supported path or leaves every target blocked with a cleaner, more stable reason. It is not successful if it broadens `JOIN` / `EXISTS` / pagination semantics or weakens multi-fragment boundaries to manufacture green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch10`: `run_7cdb98d1eb49`

Current truth:
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.existsSubquery` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.includeWithWhere` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.leftJoinWithNull` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`
- `demo.test.complex.staticGroupBy` -> `NO_SAFE_BASELINE_GROUP_BY`

## Task 1: Freeze the Batch10 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch10-intake.md`

- [x] Add `generalization-batch10` as a formal runnable batch.
- [x] Freeze the five-statement scope exactly.
- [x] Keep this step observational only.

**Success standard:** `batch10` can be refreshed and summarized without ad-hoc SQL selection.

## Task 2: Lane A — Safe-Baseline Recovery Truth

**Target:**
- `demo.test.complex.staticGroupBy`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_engine.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Freeze the current blocker for `demo.test.complex.staticGroupBy`.
- [ ] Inspect whether any existing already-supported safe-baseline path can safely carry it.
- [ ] If not, keep it in the safe-baseline lane with a more honest blocker rather than broadening group-by rewrites.

**Success standard:** `staticGroupBy` either remains a stable `NO_SAFE_BASELINE_GROUP_BY` sentinel or safely promotes through an existing supported path only.

## Task 3: Lane B — Semantic Guardrails

**Targets:**
- `demo.order.harness.listOrdersWithUsersPaged`
- `demo.test.complex.existsSubquery`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] Reconfirm that both semantic blockers are still truthful.
- [ ] Only relax comparison if equivalence is already structurally justified and evidence-backed.
- [ ] Do not weaken pagination, `JOIN`, or `EXISTS` semantics for convenience.

**Success standard:** both targets stay blocked for the same semantic class of reason, or move to an even more honest blocker without any semantic weakening.

## Task 4: Lane C — Boundary Canaries

**Targets:**
- `demo.test.complex.leftJoinWithNull`
- `demo.test.complex.includeWithWhere`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Keep `leftJoinWithNull` in the unsupported-strategy lane unless an already-supported path truly exists.
- [ ] Keep `includeWithWhere` in the safe-baseline lane unless an already-supported multi-fragment include baseline truly exists.
- [ ] Do not let candidate-selection work or semantic cleanup blur these two boundaries.

**Success standard:** both targets remain blocked for the same truthful class of reason, or move to an even more honest blocker without collateral promotion.

## Task 5: Fresh Rerun and Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch10-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch11-intake.md`

- [ ] Fresh rerun `generalization-batch10`.
- [ ] Re-run `generalization_summary.py` for `batch1..10`.
- [ ] Only create `batch11` intake after the fresh rerun confirms the next truthful dominant lane.
