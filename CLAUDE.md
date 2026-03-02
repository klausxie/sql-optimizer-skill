# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SQL Optimizer is a Python-based tool that analyzes MyBatis SQL statements, generates optimization proposals using LLM, validates them against a database, and produces XML patches for dynamic mapper templates. It's designed as an installable skill for the OpenCode platform.

## Core Commands

### Development & Testing

```bash
# Run all tests
python3 -m pytest

# Run specific test
python3 -m pytest tests/test_<name>.py

# Validate all JSON schemas
python3 scripts/schema_validate_all.py
```

### CLI Usage

The main CLI entry point is `scripts/sqlopt_cli.py`:

```bash
# Start a new optimization run
python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage patch_generate

# Check run status
python3 scripts/sqlopt_cli.py status --run-id <run_id>

# Resume an existing run
python3 scripts/sqlopt_cli.py resume --run-id <run_id>

# Apply generated patches
python3 scripts/sqlopt_cli.py apply --run-id <run_id>
```

### Skill Installation

```bash
# Build distribution bundle
python3 install/build_bundle.py

# Install to a project
python3 install/install_skill.py --project /path/to/project

# Run health check
python3 install/doctor.py --project /path/to/project
```

## Architecture

### Three-Layer Design

1. **Orchestrator** (`python/sqlopt/cli.py`, `supervisor.py`): Command routing, stage orchestration, state management, timeout/retry handling
2. **Stage Core** (`python/sqlopt/stages/`): Domain logic for each phase (scan, optimize, validate, patch_generate, report)
3. **Contracts & Artifacts** (`contracts/*.schema.json`): Schema validation, run artifacts, reporting

### Stage Pipeline

Fixed execution order: `preflight → scan → optimize → validate → patch_generate → report`

Each stage:
- Reads from previous stage artifacts in `runs/<run_id>/`
- Produces structured JSONL/JSON outputs
- Must write diagnostic events even on failure
- Never directly calls other stages (orchestrator mediates)

### Key Stages

**scan**: Extracts SQL from MyBatis XML mappers using Java scanner. Outputs `scan.sqlunits.jsonl` with both `templateSql` (template view with `<foreach>`, `<include>` tags) and `sql` (logical analysis view). Optionally outputs `scan.fragments.jsonl` when `scan.enable_fragment_catalog=true`.

**optimize**: Consumes SqlUnits, generates optimization proposals via LLM. Outputs `proposals/optimization.proposals.jsonl`. Does not generate XML patches directly.

**validate**: Validates proposals against database using EXPLAIN plans. Outputs `acceptance.results.jsonl` with semantic/performance/security judgments plus template materialization decisions (`rewriteMaterialization`, `templateRewriteOps`).

**patch_generate**: Generates XML patches. Prioritizes template-level plans from validate stage when `rewriteMaterialization.replayVerified=true`. Falls back to static SQL patches. Never overwrites dynamic templates with flat SQL.

**report**: Aggregates results into `report.md`, `report.summary.md`, `report.json` with phase status, acceptance/patch statistics, and materialization mode breakdowns.

### State Management

All runs maintain supervisor state in `runs/<run_id>/supervisor/`:
- `meta.json`: run_id, status, versions
- `plan.json`: fixed statement list and target stage
- `state.json`: per-statement phase status, retry counts, errors
- `results/*.jsonl`: structured step results for diagnostics

The orchestrator advances one statement step per invocation (bounded by `max_step_ms` budget) to avoid 120s timeout limits in OpenCode execution.

### SQL View Constraints

- `templateSql`: Source template view for dynamic template judgment and template-level patches. Not for DB execution.
- `sql`: Logical analysis view for optimize/validate. Not guaranteed to be source-writable.
- `executableSql`: Temporary view derived in validate for EXPLAIN plans. Never persisted or used as patch source.

### Template Rewrite Modes

- `STATEMENT_TEMPLATE_SAFE`: Statement-level include-safe rewrite (implemented, requires replay verification)
- `FRAGMENT_TEMPLATE_SAFE`: Fragment-level rewrite (implemented, requires `patch.template_rewrite.enable_fragment_materialization=true`)

Default: Fragment materialization is OFF (`enable_fragment_materialization=false`) but validation still outputs materialization decisions.

## Configuration

Primary config file: `sqlopt.yml` at project root

Key sections:
- `project.root_path`: Project base directory
- `scan.mapper_globs`: MyBatis XML file patterns
- `scan.java_scanner.jar_path`: Path to Java scanner JAR
- `db.platform`: Database type (postgresql, mysql, etc.)
- `db.dsn`: Database connection string
- `llm.provider`: LLM provider (`opencode_run`, `direct_openai_compatible`, `opencode_builtin`, `heuristic`)
- `runtime.profile`: Execution profile (balanced, fast, thorough)
- `patch.template_rewrite.enable_fragment_materialization`: Fragment-level template rewrite (default: false)

## Data Contracts

All stage outputs must conform to JSON schemas in `contracts/`:
- `sqlunit.schema.json`: Scanned SQL statements
- `fragment_record.schema.json`: SQL fragments catalog
- `optimization_proposal.schema.json`: Optimization candidates
- `acceptance_result.schema.json`: Validation results
- `patch_result.schema.json`: Generated patches

Schema validation failures terminate the run by default.

## Run Directory Structure

```
runs/<run_id>/
├── supervisor/
│   ├── meta.json
│   ├── plan.json
│   ├── state.json
│   └── results/
│       ├── scan.jsonl
│       ├── optimize.jsonl
│       └── ...
├── manifest.jsonl
├── scan.sqlunits.jsonl
├── scan.fragments.jsonl
├── proposals/
│   └── optimization.proposals.jsonl
├── acceptance/
│   └── acceptance.results.jsonl
├── patches/
│   └── patch.results.jsonl
├── ops/
│   ├── ops_health.json
│   └── ops_topology.json
├── report.json
├── report.md
└── report.summary.md
```

## Failure Handling

Failures are classified as:
- `fatal`: Unrecoverable, terminates run
- `retryable`: Can be retried with backoff
- `degradable`: Can continue with reduced functionality

Retry behavior controlled by `runtime.stage_retry_*` config. Completed statements are never re-executed; failed statements can be retried on resume.

## Important Constraints

1. Stages communicate only through run directory artifacts, never direct function calls
2. All stage outputs must be structured objects, not natural language
3. Dynamic template statements cannot be overwritten with flat SQL patches
4. Template-level patches require `rewriteMaterialization.replayVerified=true`
5. Each run advances one statement step per invocation to respect 120s timeout
6. Schema validation is strict by default and will fail the run on violations

## LLM Provider Options

- `opencode_run`: External `opencode run` command (default)
- `direct_openai_compatible`: Direct OpenAI-compatible API endpoint
- `opencode_builtin`: Local built-in strategy
- `heuristic`: Local simplified heuristic strategy

## Testing Notes

- Tests use fixtures in `tests/fixtures/project/`
- Some tests may fail on import if dependencies are missing (e.g., test_apply_mode.py)
- Run schema validation before committing: `python3 scripts/schema_validate_all.py`
