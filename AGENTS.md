# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

SQL Optimizer is a Python-based tool that analyzes MyBatis SQL statements, generates optimization proposals using LLM, validates them against a database, and produces XML patches for dynamic mapper templates. It's designed as an installable skill for the OpenCode platform.

Supported databases: PostgreSQL, MySQL 5.6+ (including 5.7, 8.0+; MariaDB not supported)

## Core Commands

### Development & Testing

```bash
# Run all tests (from repository root)
python3 -m pytest -q

# Run specific test
python3 -m pytest tests/test_<name>.py -v

# Run unified release acceptance
python3 scripts/ci/release_acceptance.py

# Validate all JSON schemas
python3 scripts/schema_validate_all.py

# Scan-only smoke test (validates scanner coverage)
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

### CLI Usage

The main CLI entry point is `scripts/sqlopt_cli.py`. When installed as a skill, use `~/.opencode/skills/sql-optimizer/bin/sqlopt-cli`:

```bash
# Start a new optimization run
python3 scripts/sqlopt_cli.py run --config sqlopt.yml

# Check run status
python3 scripts/sqlopt_cli.py status --run-id <run_id>

# Resume an existing run
python3 scripts/sqlopt_cli.py resume --run-id <run_id>

# Rebuild report only (when status.next_action=report-rebuild)
python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run_id>

# View verification evidence chain for a SQL statement
python3 scripts/sqlopt_cli.py verify --run-id <run_id> --sql-key <sqlKey>

# View compressed diagnostics (warnings/why_now/recommended_next_step)
python3 scripts/sqlopt_cli.py verify --run-id <run_id> --sql-key <sqlKey> --summary-only --format json

# Apply generated patches
python3 scripts/sqlopt_cli.py apply --run-id <run_id>
```

### CLI Usage

Use `sqlopt-cli` directly for optimization runs:

```bash
# Navigate to project directory with sqlopt.yml
cd /path/to/project

# Run optimization (unlimited steps/time by default)
sqlopt-cli run

# Limit steps or time
sqlopt-cli run --max-steps 5
sqlopt-cli run --max-seconds 300

# Resume previous run
sqlopt-cli resume --run-id run_xxx

# Target specific stage
sqlopt-cli run --to-stage scan
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

1. **Orchestrator** (`python/sqlopt/application/`): Command routing, stage orchestration, state management, timeout/retry handling
   - `cli.py`: CLI adapter and compatibility wrapper (delegates to application layer)
   - `workflow_engine.py`: Core workflow orchestration and phase transitions
   - `run_service.py`: Run lifecycle management
   - `run_repository.py`: Run state persistence
   - `config_service.py`: Configuration loading and validation
2. **Stage Core** (`python/sqlopt/stages/`): Domain logic for each phase (scan, optimize, validate, patch_generate, report)
3. **Contracts & Artifacts** (`contracts/*.schema.json`): Schema validation, run artifacts, reporting

### Key Architectural Boundaries

- CLI layer (`cli.py`) only contains adapter logic; core orchestration is in `application/workflow_engine.py`
- Orchestration boundary: `run_service → workflow_engine → run_repository/stages`
- Platform differences handled via strategy pattern in `preflight` and `validate` stages
- Document models: `sqlopt.platforms.sql.models` (SQL-side), `sqlopt.stages.report_interfaces` (report-side)
- External contracts exported via `to_contract()` methods

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

Primary config file: `sqlopt.yml` at project root. See `templates/sqlopt.example.yml` for reference.

### Minimal Configuration (v1)

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql  # or mysql
  dsn: postgresql://user:pass@127.0.0.1:5432/db?sslmode=disable

llm:
  enabled: true
  provider: opencode_run  # recommended
```

### Key Configuration Sections

- `project.root_path`: Project base directory
- `scan.mapper_globs`: MyBatis XML file patterns
- `scan.java_scanner.jar_path`: Path to Java scanner JAR
- `scan.class_resolution.mode`: Class resolution strategy (tolerant/strict)
- `db.platform`: Database type (postgresql, mysql)
- `db.dsn`: Database connection string
- `llm.provider`: LLM provider (`opencode_run`, `direct_openai_compatible`, `opencode_builtin`, `heuristic`)
- `llm.timeout_ms`: LLM request timeout (default: 80000ms)

### Removed Configuration Keys

The following root keys are no longer accepted: `validate`, `policy`, `apply`, `patch`, `diagnostics`, `runtime`, `verification`. These have been consolidated or removed in the current version.

### MySQL-Specific Notes

- MySQL 5.6 does not support `MAX_EXECUTION_TIME`; the system automatically degrades without blocking evidence/compare execution
- PostgreSQL dialect SQL (e.g., `ILIKE`) is not automatically rewritten for MySQL; syntax errors are reported as `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`

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
7. Report phase has `allow_regenerate=True`; other phases do not allow regeneration
8. Completed statements are never re-executed; only failed statements can be retried on resume
9. When `status.next_action=report-rebuild`, main pipeline is complete and only report needs regeneration

## Verification System

The verification system provides evidence chains and diagnostics for each SQL statement:

### Verification Commands

```bash
# View full evidence chain
sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>

# View compressed diagnostics only
sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey> --summary-only

# JSON format output
sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey> --summary-only --format json
```

### Verification Artifacts

- `verification/ledger.jsonl`: Per-statement verification records
- `verification/summary.json`: Aggregated verification summary
- Each record includes: phase, status, reason_code, evidence_refs, checks, verdict

### Verification Status Codes

- `COMPLETE`: Phase completed successfully with full verification
- `PARTIAL`: Phase completed but with degraded verification (e.g., DB unreachable)
- `FAILED`: Phase failed with error
- `SKIPPED`: Phase skipped due to upstream failure

Common reason codes:
- `VALIDATE_DB_UNREACHABLE`: Database connection failed during validation
- `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`: SQL syntax error during EXPLAIN
- `RUNTIME_STAGE_TIMEOUT`: Stage exceeded timeout limit

## LLM Provider Options

- `opencode_run`: External `opencode run` command (recommended for production)
- `direct_openai_compatible`: Direct OpenAI-compatible API endpoint
- `opencode_builtin`: Local built-in strategy (recommended for offline smoke testing)
- `heuristic`: Local simplified heuristic strategy

### LLM Enhancement Features (Phase 1-6)

All LLM enhancement phases are fully implemented and tested:

1. **Phase 1: Output Quality Control** - Syntax and heuristic validation of LLM-generated candidates
2. **Phase 2: Retry Mechanism** - Automatic retry with feedback on validation failures
3. **Phase 3: Semantic Check** - LLM-based semantic equivalence verification when DB validation fails
4. **Phase 4: Feedback Collection** - Bidirectional feedback between rule engine and LLM (logged to `ops/llm_feedback.jsonl`)
5. **Phase 5: Patch Generation Assist** - LLM assistance for dynamic SQL template suggestions
6. **Phase 6: Trace Enhancement** - Complete LLM interaction history recording

Note: LLM enhancement features are now integrated into the main pipeline and controlled internally. User configuration for these features has been removed.

Test coverage: 84 new tests covering all LLM enhancement features

## Testing Notes

- Tests use fixtures in `tests/fixtures/project/`
- 64 test files covering all stages and LLM enhancements
- Run from repository root: `python3 -m pytest -q`
- Unified acceptance: `python3 scripts/ci/release_acceptance.py`
- Individual acceptance tests:
  - `python3 scripts/ci/opencode_smoke_acceptance.py`
  - `python3 scripts/ci/degraded_runtime_acceptance.py`
  - `python3 scripts/ci/report_rebuild_acceptance.py`
- Schema validation before committing: `python3 scripts/schema_validate_all.py`
- Some tests may fail on import if dependencies are missing (e.g., test_apply_mode.py)

### Scanner Coverage Validation

The scanner supports these MyBatis dynamic tags (validated in fixtures):
- `bind`
- `choose/when/otherwise`
- `where`
- `if`
- `foreach`
- `include`
- `trim`
- `set`

Verify scanner output:
- `tests/fixtures/project/runs/<run_id>/scan.sqlunits.jsonl`
- `tests/fixtures/project/runs/<run_id>/scan.fragments.jsonl`
- `tests/fixtures/project/runs/<run_id>/verification/ledger.jsonl`

### MySQL Local Testing

Quick MySQL test database setup:

```bash
mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
```

This creates and populates tables: `users`, `orders`, `shipments`

## PYTHONPATH Setup

When running scripts directly (not via installed skill), set PYTHONPATH:

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml
```

The repository root contains `python/sqlopt/` as the main package directory.

## Documentation References

For detailed information, refer to:
- `docs/QUICKSTART.md`: 10-minute getting started guide
- `docs/INDEX.md`: Complete documentation index organized by role and topic
- `docs/INSTALL.md`: Detailed installation instructions
- `docs/project/01-product-requirements.md`: Product requirements and goals
- `docs/project/02-system-spec.md`: System specification
- `docs/project/03-workflow-and-state-machine.md`: Workflow and state management
- `docs/project/04-data-contracts.md`: Data contracts and schemas
- `docs/project/05-config-and-conventions.md`: Configuration options detailed reference
- `docs/project/06-delivery-checklist.md`: Delivery and deployment checklist
- `docs/project/08-artifact-governance.md`: Run artifacts and source-of-truth rules
- `docs/TROUBLESHOOTING.md`: Common issues and solutions
- `docs/UPGRADE.md`: Version upgrade guide
- `docs/DISTRIBUTION.md`: Packaging and distribution guide

## Priority Rules (in case of conflicts)

1. `contracts/*.schema.json` (highest priority)
2. Current code verifiable behavior (`python/sqlopt`, `scripts/sqlopt_cli.py`)
3. Historical documentation (`docs/*.md`)
