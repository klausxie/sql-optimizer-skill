# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

SQL Optimizer analyzes MyBatis SQL, proposes rewrites with LLM or heuristics, validates candidates against a database, and generates XML patches.

Supported databases:
- PostgreSQL
- MySQL 5.6+ / 5.7 / 8.0+
- MariaDB is not supported

## Core Commands

```bash
# Full test suite
python3 -m pytest -q

# Schema validation
python3 scripts/schema_validate_all.py

# Unified acceptance
python3 scripts/ci/release_acceptance.py

# Scan smoke on sample project
python3 scripts/run_sample_project.py \
  --config tests/fixtures/configs/sample_project/scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

Main CLI:

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml
python3 scripts/sqlopt_cli.py status --run-id <run_id>
python3 scripts/sqlopt_cli.py resume --run-id <run_id>
python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run_id>
python3 scripts/sqlopt_cli.py verify --run-id <run_id> --sql-key <sqlKey>
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id <run_id>
```

## Architecture

Three layers:
- `python/sqlopt/application/`
  Orchestration, lifecycle, command routing
- `python/sqlopt/stages/`
  Stage logic: `scan -> optimize -> validate -> patch_generate -> report`
- `contracts/**/*.schema.json`
  Stable artifact contracts

Key boundaries:
- CLI adapter logic stays thin; orchestration belongs in `application/`
- Stages communicate through run artifacts, never direct stage-to-stage calls
- Template patches must come from validate/patch facts, never from flattened executable SQL

## Run Layout

Canonical run structure:

```text
runs/<run_id>/
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
    └── <sql-key>/index.json
```

Rules:
- `control/state.json` is the run state source of truth
- `control/manifest.jsonl` is the execution history
- `report.json` is a minimal summary, not a replay source
- verification payloads are embedded in stage artifacts; there is no standalone verification ledger directory

## Stage Notes

- `scan`
  Writes `artifacts/scan.jsonl`; optional fragment catalog goes to `artifacts/fragments.jsonl`
- `optimize`
  Writes `artifacts/proposals.jsonl`
- `validate`
  Writes `artifacts/acceptance.jsonl` with semantic/performance/security decisions plus rewrite facts
- `patch_generate`
  Writes `artifacts/patches.jsonl`; never overwrites dynamic templates with flat SQL
- `report`
  Writes minimal `report.json` plus `sql/` indexes

Template rewrite modes:
- `STATEMENT_TEMPLATE_SAFE`
- `FRAGMENT_TEMPLATE_SAFE`

Fragment materialization is off by default.

## Configuration

Primary config: `sqlopt.yml`

Minimal shape:

```yaml
config_version: v1
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db?sslmode=disable
llm:
  enabled: true
  provider: opencode_run
```

Important keys:
- `project.root_path`
- `scan.mapper_globs`
- `scan.java_scanner.jar_path`
- `scan.class_resolution.mode`
- `db.platform`
- `db.dsn`
- `llm.provider`
- `llm.timeout_ms`

Removed root keys:
- `validate`
- `policy`
- `apply`
- `patch`
- `diagnostics`
- `runtime`
- `verification`

MySQL notes:
- MySQL 5.6 lacks `MAX_EXECUTION_TIME`; system degrades without blocking evidence collection
- PostgreSQL-only syntax is not rewritten automatically for MySQL

## Constraints

1. Stage outputs must be structured data, not prose.
2. Schema validation is strict by default.
3. Completed statements are not re-executed on resume.
4. Report regeneration is the only allowed rebuild path after pipeline completion.
5. `status.next_action=report-rebuild` means pipeline work is done and only report needs regeneration.

## Tests And Harness

Test layout:
- `tests/unit/`
- `tests/contract/classification|patch|report|schema`
- `tests/harness/engine|workflow|fixture`
- `tests/ci/`

Static fixture assets:
- `tests/fixtures/projects/sample_project/`
- `tests/fixtures/scenarios/sample_project.json`
- `tests/fixtures/configs/sample_project/`

Harness implementation lives in `python/sqlopt/devtools/harness/`:
- `runtime/`
- `assertions/`
- `scenarios/`
- `benchmark/`

Relationship:
- `tests/harness/engine/` verifies the harness implementation itself
- `tests/harness/workflow/` verifies workflow control scenarios
- `tests/harness/fixture/` verifies sample-project scenarios

## Verification

Useful command:

```bash
python3 scripts/sqlopt_cli.py verify --run-id <run_id> --sql-key <sqlKey> --summary-only --format json
```

Verification records are embedded in:
- `artifacts/scan.jsonl`
- `artifacts/proposals.jsonl`
- `artifacts/acceptance.jsonl`
- `artifacts/patches.jsonl`

## Docs

Current docs:
- `docs/INDEX.md`
- `docs/QUICKSTART.md`
- `docs/INSTALL.md`
- `docs/CONFIG.md`
- `docs/TROUBLESHOOTING.md`
- `docs/current-spec.md`

Priority when docs and code disagree:
1. `contracts/**/*.schema.json`
2. Current code under `python/sqlopt` and `scripts/sqlopt_cli.py`
3. Documentation
