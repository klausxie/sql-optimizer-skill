# Run Layout Simplification Design

Date: 2026-04-01

## Context

The current `runs/<run-id>/` layout exposes too many parallel views of the same run:

- human-facing summaries under `overview/`
- machine-facing indexes under `run.index.json` and `diagnostics/`
- stage outputs under `pipeline/`
- verification evidence under `pipeline/verification/`
- per-SQL drill-down under `sql/`

This creates two problems:

1. Directory browsing is noisy because one run emits many top-level concepts and several near-duplicate summaries.
2. Artifact ownership is blurred because summary, navigation, diagnostics, and evidence are split across multiple folders.

The goal of this redesign is not backward compatibility. The goal is an aggressively smaller canonical run layout.

## Goals

1. Reduce the run directory to the minimum durable artifact set.
2. Make one file the obvious run entry point.
3. Preserve clear separation between runtime control, stage outputs, and per-SQL drill-down.
4. Remove duplicate summary, index, and diagnostics layers.

## Non-Goals

1. Preserve existing canonical paths.
2. Keep Markdown reports in this iteration.
3. Keep a standalone verification ledger directory.
4. Provide legacy dual-write or compatibility reads.

## Target Layout

```text
runs/<run-id>/
├── report.json
├── control/
│   ├── state.json
│   ├── plan.json
│   └── manifest.jsonl
├── artifacts/
│   ├── scan.jsonl
│   ├── fragments.jsonl
│   ├── proposals.jsonl
│   ├── acceptance.jsonl
│   └── patches.jsonl
└── sql/
    ├── catalog.jsonl
    └── <sql-key>/
        └── index.json
```

## Design Summary

### `report.json`

`report.json` is the only run-level summary file. It is intentionally minimal and does not act as a directory index.

It keeps only:

- run identity and generation time
- target stage
- overall status and verdict
- next action
- phase status summary
- compact run statistics
- top blocker codes

It does not keep:

- resolved config
- large SQL outcome lists
- artifact path indexes
- verification ledgers or verification detail payloads
- ops topology or health detail
- Markdown-rendered report content

Representative shape:

```json
{
  "run_id": "run_xxx",
  "generated_at": "2026-04-01T12:00:00+08:00",
  "target_stage": "report",
  "status": "DONE",
  "verdict": "PARTIAL",
  "next_action": "resume",
  "phase_status": {
    "scan": "DONE",
    "optimize": "DONE",
    "validate": "DONE",
    "patch_generate": "DONE",
    "report": "DONE"
  },
  "stats": {
    "sql_total": 120,
    "proposal_total": 45,
    "accepted_total": 18,
    "patchable_total": 9,
    "patched_total": 6,
    "blocked_total": 102
  },
  "blockers": {
    "top_reason_codes": [
      {"code": "VALIDATE_PERF_NOT_IMPROVED", "count": 12},
      {"code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", "count": 1}
    ]
  }
}
```

### `control/`

`control/` is the only runtime control surface.

- `state.json` is the single source of truth for current run state and per-SQL phase progress.
- `plan.json` defines the fixed execution target and SQL set for the run.
- `manifest.jsonl` is the only append-only execution history stream.

This folder replaces:

- `pipeline/supervisor/`
- `pipeline/supervisor/results/`
- `pipeline/ops/`

Operational failures, retries, degradations, and stage transitions are written into `manifest.jsonl` instead of fragmented sidecar ledgers.

### `artifacts/`

`artifacts/` contains direct stage outputs only.

- `scan.jsonl`
- `fragments.jsonl`
- `proposals.jsonl`
- `acceptance.jsonl`
- `patches.jsonl`

Rules:

1. These files express stage facts, not run summary.
2. These files may be deleted and recomputed.
3. These files do not own navigation or global diagnostic roles.

The old standalone verification ledger is removed. Evidence fields that remain necessary should be folded into `acceptance.jsonl` and `patches.jsonl` records directly.

### `sql/`

`sql/` remains the drill-down area, but only as a thin per-SQL index surface.

- `catalog.jsonl` is the global SQL index.
- `sql/<sql-key>/index.json` is the single entry point for one SQL item.

`catalog.jsonl` should keep a small field set:

- `sql_key`
- `statement_key`
- `delivery_status`
- `sql_path`

`sql/<sql-key>/index.json` may reference deep evidence such as trace files or candidate-generation diagnostics, but those deep files should not participate in top-level navigation.

## Explicit Removals

The following layers are removed entirely:

- `overview/`
- `diagnostics/`
- `pipeline/verification/`
- `pipeline/ops/`
- `pipeline/supervisor/results/`
- `run.index.json`
- `report.md`
- `report.summary.md`

The following path families are flattened into `artifacts/`:

- `pipeline/scan/sqlunits.jsonl` -> `artifacts/scan.jsonl`
- `pipeline/scan/fragments.jsonl` -> `artifacts/fragments.jsonl`
- `pipeline/optimize/optimization.proposals.jsonl` -> `artifacts/proposals.jsonl`
- `pipeline/validate/acceptance.results.jsonl` -> `artifacts/acceptance.jsonl`
- `pipeline/patch_generate/patch.results.jsonl` -> `artifacts/patches.jsonl`

## Source Of Truth Mapping

The redesigned layout uses these ownership rules:

1. Current run state: `control/state.json`
2. Fixed run plan: `control/plan.json`
3. Execution history: `control/manifest.jsonl`
4. Run summary: `report.json`
5. Stage facts: `artifacts/*.jsonl`
6. Per-SQL drill-down entry: `sql/catalog.jsonl` and `sql/<sql-key>/index.json`

No other file should evolve into a second state source, second summary source, or second index layer.

## Data Flow

1. Runtime orchestration updates `control/state.json`.
2. Every meaningful execution event appends one record to `control/manifest.jsonl`.
3. Each stage writes its direct result file under `artifacts/`.
4. Report aggregation reads `control/` and `artifacts/`, then writes `report.json`.
5. SQL-specific aggregation writes `sql/catalog.jsonl` and per-SQL `index.json`.

## Error Handling

1. Partial, degraded, retryable, and fatal outcomes are all recorded through `control/manifest.jsonl`.
2. Stage-specific evidence remains attached to stage output rows instead of being duplicated into standalone diagnostic ledgers.
3. `report.json` only surfaces compact blocker summaries and next action hints; it does not become a full debug dump.

## Migration Strategy

This is a breaking migration.

Rules:

1. No legacy dual-write.
2. No compatibility reader for old paths.
3. All readers switch in one change set.
4. Old directories are deleted rather than kept as transitional aliases.

Affected read paths include at minimum:

- CLI status/resume/verify/apply flows
- report loading and rendering code
- schema validation scripts
- acceptance tests
- fixture project run artifacts

## Verification Strategy

The migration is accepted only if these checks pass:

1. A full run completes and emits the new directory layout only.
2. `status`, `resume`, `verify`, and `apply` read only new paths.
3. Acceptance, patch, and report statistics remain semantically equivalent to current behavior.
4. Per-SQL drill-down still works from `sql/catalog.jsonl` to `sql/<sql-key>/index.json`.

## Testing Strategy

Required coverage:

1. Run path unit tests for the new canonical structure.
2. Report builder and loader tests against the new file set.
3. CLI integration tests for `status`, `resume`, `verify`, and `apply`.
4. Fixture-based end-to-end tests proving the old layout is no longer written.
5. Schema validation updates for the reduced contract set.

## Implementation Notes

The main engineering risk is not path renaming. The main risk is allowing removed concepts to leak back under new names.

Guardrails:

1. Do not recreate a second summary file beside `report.json`.
2. Do not recreate a second event ledger beside `control/manifest.jsonl`.
3. Do not recreate a second verification index beside stage output rows.
4. Keep `report.json` intentionally small even if more detail is available elsewhere.
