# Generalization Batch8 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch8` as a blocker program centered on the truthful lanes visible in the fresh replay baseline:

1. `NO_SAFE_BASELINE_RECOVERY`
2. `SEMANTIC_PREDICATE_CHANGED`
3. `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`

This program is successful if it either promotes a target through an already-supported safe path or leaves it blocked with a cleaner, more stable reason. It is not successful if it broadens choose/foreach/join semantics just to create green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch8`: `run_a1436100774b`

Current view:
- `AUTO_PATCHABLE = 0`
- `MANUAL_REVIEW = 5`
- `decision_focus = NO_SAFE_BASELINE_RECOVERY`
- `recommended_next_step = clarify_safe_baseline_recovery_paths`

Per-statement truth:
- `demo.user.advanced.findUsersByKeyword` -> `NO_SAFE_BASELINE_RECOVERY`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_RECOVERY`
- `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_RECOVERY`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`
- `demo.test.complex.inSubquery` -> `NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY`

## Task 1: Freeze the Batch8 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/generalization_blocker_inventory.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/fixtures/scenarios/sample_project.json`

- [ ] Add a `POST_BATCH8_SENTINELS` registry section with:
  - `POST_BATCH8_SAFE_BASELINE_SENTINELS`
  - `POST_BATCH8_CANDIDATE_SENTINELS`
  - `POST_BATCH8_SEMANTIC_SENTINELS`
- [ ] Freeze exact primary blockers for the five batch8 statements in fixture scenario expectations.
- [ ] Keep this observational only.

**Success standard:** batch8 can be summarized without re-reading notes.

## Task 2: Lane A — Safe-Baseline Recovery Clarity

**Targets:**
- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Prove whether any of these three statements already map to an existing supported safe baseline.
- [ ] If not, keep them at `NO_SAFE_BASELINE_RECOVERY` with cleaner diagnostics.
- [ ] Guard against leaking plain `FOREACH/INCLUDE` and fragment-chain boundaries into this lane.

**Success standard:** these statements either remain stable `NO_SAFE_BASELINE_RECOVERY` sentinels or safely promote through existing baseline families only.

## Task 3: Lane B — Semantic Comparison Weakness

**Targets:**
- `demo.order.harness.listOrdersWithUsersPaged`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_verification_stage_integration.py`

- [ ] Distinguish whether `SEMANTIC_PREDICATE_CHANGED` is a true semantic blocker or an overly strict comparison.
- [ ] Relax only if equivalence is already structurally justified and evidence-backed.
- [ ] Keep join/exists/offset-risk non-goals blocked.

**Success standard:** the target ends either as a justified semantic blocker, a more accurate blocker, or ready through already-justified semantics.

## Task 3b: Lane C — Unsupported Strategy Cleanup

**Target:**
- `demo.test.complex.inSubquery`

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_support.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_candidate_generation_engine.py`

- [ ] Keep `IN`-subquery rewrite wording drift (`subquery_to_exists`, `subquery_to_join`) inside the unsupported-strategy bucket.
- [ ] Do not broaden semantic comparison to rescue this target.

**Success standard:** `inSubquery` no longer looks like a semantic blocker unless a future run introduces genuinely semantic candidates.

## Task 4: Fresh Rerun and Next Intake

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch8-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch9-intake.md`

- [ ] Fresh rerun `generalization-batch8`.
- [ ] Re-run `generalization_summary.py` for `batch1..8`.
- [ ] Only create `batch9` intake after the fresh rerun confirms the next truthful dominant lane.
