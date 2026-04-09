# Generalization Batch13 Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This program keeps the current run/artifact model and blocked-boundary registry intact.

**Goal:** Execute `generalization-batch13` as a final boundary-clarification batch centered on the truthful lanes visible in the fresh replay baseline:

1. safe-baseline guardrail for `NO_SAFE_BASELINE_*`
2. validate/semantic guardrail for `VALIDATE_SEMANTIC_ERROR`
3. semantic guardrail for `SEMANTIC_PREDICATE_CHANGED`

This program is successful if it leaves the five targets blocked with the same or cleaner truthful reasons. It is not successful if it broadens choose/include recovery or weakens pagination semantics to manufacture green statements.

## Fresh Baseline

Fresh replay run:
- `generalization-batch13`: `run_c5294ca22116`

Current truth:
- `demo.user.advanced.findUsersByKeyword` -> `NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER`
- `demo.shipment.harness.findShipments` -> `NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY`
- `demo.test.complex.multiFragmentLevel1` -> `NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE`
- `demo.test.complex.includeNested` -> `VALIDATE_SEMANTIC_ERROR`
- `demo.order.harness.listOrdersWithUsersPaged` -> `SEMANTIC_PREDICATE_CHANGED`

## Task 1: Freeze the Batch13 Sentinel Set

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/sample_project_family_scopes.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_run_sample_project_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_refresh_script.py`
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch13-intake.md`

- [x] Add `generalization-batch13` as a formal runnable batch.
- [x] Freeze the five-statement scope exactly.
- [x] Keep this step observational only.

**Success standard:** `batch13` can be refreshed and summarized without ad-hoc SQL selection.

## Task 2: Lane A — Safe-Baseline Guardrails

**Targets:**
- `demo.user.advanced.findUsersByKeyword`
- `demo.shipment.harness.findShipments`
- `demo.test.complex.multiFragmentLevel1`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Keep each target in its current safe-baseline subtype unless stronger evidence supports an even narrower truthful blocker.
- [ ] Do not broaden choose-guarded, speculative-limit, or multi-fragment include recovery.

**Success standard:** all three stay blocked for the same safe-baseline class of reason, or move to an even more honest blocker without new recovery paths.

## Task 3: Lane B — Validate/Semantic Include Guardrail

**Target:**
- `demo.test.complex.includeNested`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/verification/test_validate_convergence.py`

- [ ] Reconfirm that `VALIDATE_SEMANTIC_ERROR` remains truthful.
- [ ] Do not turn nested include validation failure into candidate-selection or safe-baseline work.

**Success standard:** `includeNested` remains blocked for the same truthful class of reason, or moves to an even more honest validate blocker without broad include recovery.

## Task 4: Lane C — Semantic Canary

**Target:**
- `demo.order.harness.listOrdersWithUsersPaged`

**Files:**
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/platforms/sql/semantic_equivalence.py`
- Modify only if required: `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/stages/validate_convergence.py`
- Test: `/Users/klaus/Desktop/sql-optimizer-skill/tests/unit/sql/test_semantic_equivalence.py`

- [ ] Keep `listOrdersWithUsersPaged` blocked unless an evidence-backed semantic fix exists.
- [ ] Do not weaken pagination or predicate semantics for convenience.

**Success standard:** the semantic canary stays blocked for the same semantic class of reason, or moves to an even more honest blocker without semantic weakening.

## Task 5: Fresh Rerun and Phase Review

**Files:**
- Modify: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-batch13-program.md`
- Create: `/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/plans/2026-04-09-generalization-phase-review.md`

- [ ] Fresh rerun `generalization-batch13`.
- [ ] Re-run `generalization_summary.py` for `batch1..13`.
- [ ] Write the phase review instead of automatically opening `batch14`.
