# Productization / Boundary Hardening Implementation Plan

## Goal

Implement the smallest concrete changes needed to make the current optimizer boundary visible, stable, and enforceable in summary/diagnostics output.

This plan executes the specs:

- [2026-04-10-supported-capability-matrix.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-10-supported-capability-matrix.md)
- [2026-04-10-product-output-boundary-mapping.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-10-product-output-boundary-mapping.md)
- [2026-04-10-release-gate-definition.md](/Users/klaus/Desktop/sql-optimizer-skill/docs/superpowers/specs/2026-04-10-release-gate-definition.md)

## Architecture

Keep the current run/artifact model intact.

Do not change patchability rules, convergence semantics, or replay contracts.

Only improve:

- product-facing boundary expression
- summary/diagnostics wording
- release-gate enforcement

Do not change the formal `report.json` contract in this plan.

## Implementation Tasks

### Task 1: Add Product Boundary Mapping To Summary/Diagnostics Output

Introduce product-facing boundary fields alongside existing raw engineering fields.

Likely touch points:

- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/devtools/run_progress_summary.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/generalization_summary.py`
- `/Users/klaus/Desktop/sql-optimizer-skill/python/sqlopt/application/diagnostics_summary.py`

Expected additions:

- `boundaryCategory`
- `boundarySummary`
- `recommendedAction`

Rules:

- preserve raw `conflictReason`
- preserve existing `decision_focus` and `recommended_next_step`
- add product fields, do not replace engineering ones

Tests:

- summary script tests for representative blocked lanes
- diagnostics summary tests for representative supported and blocked lanes

### Task 2: Add Provider-Limited And Boundary-Specific Mapping Rules

Implement the narrow mappings defined in the spec:

- semantic reasons -> `SEMANTIC_BOUNDARY`
- validate reasons -> `VALIDATE_SECURITY_BOUNDARY`
- frozen non-goals -> `FROZEN_NON_GOAL`
- deferred capability lanes -> `DEFERRED_CAPABILITY`
- choose-local primary sentinel -> `PROVIDER_LIMITED`

Important constraint:

- `NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY` must not globally map to `PROVIDER_LIMITED`
- only the explicitly frozen choose-local lane gets that category

Tests:

- primary provider-limited sentinel
- one frozen non-goal
- one semantic boundary
- one validate/security boundary
- one supported sentinel

### Task 3: Add Release-Gate Assertions

Turn the release-gate spec into small executable checks.

Likely touch points:

- `/Users/klaus/Desktop/sql-optimizer-skill/tests/ci/test_generalization_summary_script.py`
- possibly a new CI-oriented helper under `/Users/klaus/Desktop/sql-optimizer-skill/scripts/ci/`

Minimum assertions:

- ready sentinels remain ready
- blocked boundaries do not become patchable
- product boundary categories remain aligned with current truth

This does not require a new big CI pipeline.

It only needs enough executable protection that future changes cannot silently drift.

### Task 4: Surface The Supported Capability Matrix In Docs

Integrate the supported capability matrix into the main documentation surface.

Likely touch points:

- `/Users/klaus/Desktop/sql-optimizer-skill/docs/INDEX.md`
- `/Users/klaus/Desktop/sql-optimizer-skill/docs/QUICKSTART.md`
- optionally `/Users/klaus/Desktop/sql-optimizer-skill/docs/current-spec.md`

Goal:

- make the supported scope discoverable without reading superpowers plans first

## Verification Plan

### During Implementation

Run narrow tests first:

- summary/diagnostics tests
- diagnostics summary tests
- targeted CI tests for boundary mapping

### Before Completion

Run:

```bash
python3 -m pytest -q
```

And, if summary behavior changes:

```bash
python3 scripts/ci/generalization_summary.py --batch-run generalization-batch13=tests/fixtures/projects/sample_project/runs/<run_id> --format text
```

using a known current run to inspect rendered output shape.

## Success Criteria

- product-facing summary/diagnostics output includes stable boundary categories
- raw engineering truth is preserved
- release-gate tests protect ready and blocked truths
- docs expose the supported scope and blocked-boundary language
- no capability behavior changes are introduced

## Hard Stop

Stop if implementation starts requiring:

- new patch families
- convergence logic changes
- replay/materialization behavior changes
- new exploratory batches

That would mean the work has drifted back into capability development instead of productization.
