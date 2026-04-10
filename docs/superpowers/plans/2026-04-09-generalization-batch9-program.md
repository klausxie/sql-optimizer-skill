# Generalization Batch9 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch9` as a blocker program centered on `NO_SAFE_BASELINE_RECOVERY`, while preserving one semantic canary.

Active lanes:

1. `NO_SAFE_BASELINE_RECOVERY`
2. semantic guardrail for `SEMANTIC_PREDICATE_CHANGED`

This program is successful if it either promotes a target through an already-supported safe path or leaves it blocked with a cleaner, more stable reason. It is not successful if it broadens choose/foreach/join semantics or weakens semantic comparison to manufacture green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch8`: `run_a1436100774b`

Current truth:
- `demo.user.advanced.findUsersByKeyword` -> `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.order.harness.findOrdersByUserIdsAndStatus` -> `NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

## Task 1: Freeze the Batch9 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch9-intake.md`

- [ ] Add `generalization-batch9` as a formal runnable batch.
- [ ] Freeze the five-statement scope exactly.
- [ ] Keep this step observational only.

**Success standard:** `batch9` can be refreshed and summarized without ad-hoc SQL selection.

## Task 2: Lane A — Safe-Baseline Recovery Truth

**Targets:**
- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`
- `demo.order.harness.findOrdersByUserIdsAndStatus`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Prove whether any of the four statements already map to an existing supported safe baseline family.
- [ ] If not, keep them in the `NO_SAFE_BASELINE_*` lane with clearer diagnostics.
- [ ] Guard against leaking plain `FOREACH/INCLUDE`, fragment-chain, and choose-generalization boundaries into this lane.

**Success standard:** each target either remains a stable `NO_SAFE_BASELINE_*` sentinel or safely promotes through an existing baseline family only.

## Task 3: Lane B — Semantic Guardrail

**Target:**
- `demo.order.harness.listOrdersWithUsersPaged`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] Reconfirm that `SEMANTIC_PREDICATE_CHANGED` is still a truthful blocker.
- [ ] Do not relax semantic comparison unless the equivalence is already structurally justified and evidence-backed.

**Success standard:** the target stays blocked for the same semantic class of reason, or moves to an even more honest blocker without any semantic weakening.

## Task 4: Fresh Rerun and Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch9-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch10-intake.md`

- [ ] Fresh rerun `generalization-batch9`.
- [ ] Re-run `generalization_summary.py` for `batch1..9`.
- [ ] Only create `batch10` intake after the fresh rerun confirms the next truthful dominant lane.
