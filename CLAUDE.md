# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

### V8 Seven-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              V8 Pipeline                                                  │
│  Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch               │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Stage | Name | Description |
|-------|------|-------------|
| 1 | Discovery | Connect DB, parse MyBatis XML, extract SQL |
| 2 | Branching | Expand dynamic tags to execution branches (if/choose/foreach) |
| 3 | Pruning | Static analysis, risk marking, low-value branch filtering |
| 4 | Baseline | EXPLAIN plan collection, performance baseline |
| 5 | Optimize | Rule engine + LLM generates optimization proposals |
| 6 | Validate | Semantic verification, performance comparison |
| 7 | Patch | Generate XML patches, user confirmation, apply changes |

### Key Architectural Boundaries

- **Orchestrator** (`python/sqlopt/application/`): Command routing, stage orchestration, state management
  - `workflow_v8.py`: V8 workflow orchestration (replaces old `workflow_engine.py`)
  - `run_service.py`: Run lifecycle management
  - `run_repository.py`: Run state persistence
  - `config_service.py`: Configuration loading and validation
- **Stages** (`python/sqlopt/stages/`): Domain logic for each phase
  - `discovery/`, `branching/`, `pruning/`, `baseline/`, `optimize/`, `validate/`, `patch/`, `report/`
- **Contracts** (`contracts/*.schema.json`): Schema validation, run artifacts, reporting

### Stage Pipeline

Fixed execution order: `Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch`

Each stage:
- Reads from previous stage artifacts in `runs/<run_id>/`
- Produces structured JSONL/JSON outputs
- Must write diagnostic events even on failure
- Never directly calls other stages (orchestrator mediates)

### Key Stages

**Discovery**: Connects to DB, collects table schemas, parses MyBatis XML files, extracts SQL statements. Outputs `scan.sqlunits.jsonl` and `sqlmap_catalog/` index.

**Branching**: Expands dynamic SQL into concrete execution branches. Supports three strategies: `all_combinations`, `pairwise`, `boundary`. Outputs `branches/<sql_key>.json` with branch data.

**Pruning**: Static analysis detecting performance issues:
- `prefix_wildcard`: `LIKE '%value'` - HIGH risk (cannot use index)
- `suffix_wildcard_only`: `LIKE 'value%'` - LOW risk
- `concat_wildcard`: `CONCAT('%', name)` - HIGH risk
- `function_wrap`: `UPPER(col)`, `YEAR(date)` - MEDIUM risk (index失效)
- `select_star`: `SELECT *` - MEDIUM risk

Outputs `risks/<sql_key>.json`.

**Baseline**: Executes EXPLAIN, collects performance data (execution time, rows scanned, result hash). Outputs `baseline/<sql_key>.json`.

**Optimize**: Rule engine + LLM generates optimization proposals. Outputs `proposals/<sql_key>/prompt.json` and `proposals/<sql_key>/proposal.json`.

**Validate**: Semantic equivalence verification, performance comparison, result set validation. Outputs `acceptance/<sql_key>.json` and `verification/<sql_key>.json`.

**Patch**: Generates MyBatis XML patches. Supports user confirmation before applying. Outputs `patches/<sql_key>/patch.xml`.

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

### Branching Strategies

- `all_combinations`: All conditional combinations
- `pairwise`: Pairwise combinations (two-by-two)
- `boundary`: Boundary value combinations

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
- `scan.java_scanner.jar_path`: Path to Java scanner JAR (deprecated, V8 uses pure Python)
- `scan.class_resolution.mode`: Class resolution strategy (tolerant/strict)
- `db.platform`: Database type (postgresql, mysql)
- `db.dsn`: Database connection string
- `llm.provider`: LLM provider (`opencode_run`, `direct_openai_compatible`, `opencode_builtin`, `heuristic`)
- `llm.timeout_ms`: LLM request timeout (default: 80000ms)

### Stage Configuration

```yaml
stages:
  discovery:
    enabled: true
    cache_schema: true
    
  branching:
    strategy: all_combinations  # all_combinations | pairwise | boundary
    max_branches: 100
    
  pruning:
    risk_threshold: medium  # high | medium | low
    
  baseline:
    timeout_ms: 5000
    sample_size: 100
    
  optimize:
    llm_provider: opencode_run
    max_candidates: 3
    
  validate:
    verify_semantics: true
    verify_performance: true
    
  patch:
    auto_backup: true
    require_confirm: true
```

### Removed Configuration Keys

The following root keys are no longer accepted: `validate`, `policy`, `apply`, `patch`, `diagnostics`, `runtime`, `verification`. These have been consolidated into the `stages` section or removed in V8.

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
├── supervisor/                           # Run state (shared by all stages)
│   ├── meta.json                        # Run metadata
│   ├── plan.json                        # SQL execution plan
│   ├── state.json                       # Stage state
│   └── results/                         # Step results
│
├── scan.sqlunits.jsonl                   # [Stage 1] SQL unit list
├── sqlmap_catalog/                       # [Stage 1] SQL fragment catalog
│   ├── index.json                       # Index file
│   └── <sql_key>.json                   # Individual SQL details
│
├── branches/                             # [Stage 2] Branch data
│   └── <sql_key>.json                   # Individual SQL branches
│
├── risks/                                # [Stage 3] Risk data
│   └── <sql_key>.json                   # Individual SQL risks
│
├── baseline/                             # [Stage 4] Performance baseline
│   └── <sql_key>.json                   # Individual SQL baseline
│
├── proposals/                            # [Stage 5] Optimization proposals
│   └── <sql_key>/
│       ├── prompt.json                  # LLM prompt
│       └── proposal.json                # LLM optimization proposal
│
├── acceptance/                           # [Stage 6] Validation results
│   └── <sql_key>.json                   # Individual SQL validation result
│
├── verification/                         # [Stage 6] Verification evidence
│   └── <sql_key>.json                   # Verification evidence
│
├── patches/                              # [Stage 7] Patch files
│   └── <sql_key>/
│       └── patch.xml                    # Generated XML patch
│
├── report.json                           # [Stage 7] JSON report
├── report.md                             # [Stage 7] Markdown report
└── report.summary.md                    # [Stage 7] Summary report
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
4. V8 uses pure Python scanner (no Java dependency)
5. Each run advances one statement step per invocation to respect 120s timeout
6. Schema validation is strict by default and will fail the run on violations
7. Branching supports three strategies: `all_combinations`, `pairwise`, `boundary`
8. Pruning detects: prefix_wildcard, suffix_wildcard_only, concat_wildcard, function_wrap, select_star
9. Completed statements are never re-executed; only failed statements can be retried on resume

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

- `verification/<sql_key>.json`: Per-statement verification records
- `acceptance/<sql_key>.json`: Validation results with semantic/performance/security judgments

Each record includes: phase, status, reason_code, evidence_refs, checks, verdict

### Verification Status Codes

- `COMPLETE`: Phase completed successfully with full verification
- `PARTIAL`: Phase completed but with degraded verification (e.g., DB unreachable)
- `FAILED`: Phase failed with error
- `SKIPPED`: Phase skipped due to upstream failure

Common reason codes:
- `VALIDATE_DB_UNREACHABLE`: Database connection failed during validation
- `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`: SQL syntax error during EXPLAIN
- `RUNTIME_STAGE_TIMEOUT`: Stage exceeded timeout limit
- `BRANCHING_MAX_BRANCHES_EXCEEDED`: Branch count exceeded max_branches limit

## LLM Provider Options

- `opencode_run`: External `opencode run` command (recommended for production)
- `direct_openai_compatible`: Direct OpenAI-compatible API endpoint
- `opencode_builtin`: Local built-in strategy (recommended for offline smoke testing)
- `heuristic`: Local simplified heuristic strategy

### LLM Enhancement Features

All LLM enhancement phases are implemented in the Optimize stage:

1. **Output Quality Control** - Syntax and heuristic validation of LLM-generated candidates
2. **Retry Mechanism** - Automatic retry with feedback on validation failures
3. **Semantic Check** - LLM-based semantic equivalence verification when DB validation fails
4. **Feedback Collection** - Bidirectional feedback between rule engine and LLM (logged to `proposals/<sql_key>/feedback.jsonl`)
5. **Patch Generation Assist** - LLM assistance for dynamic SQL template suggestions
6. **Trace Enhancement** - Complete LLM interaction history recording

Configuration:
- `stages.optimize.llm_provider`: LLM provider selection
- `stages.optimize.max_candidates`: Maximum optimization candidates to generate
- `stages.validate.llm_semantic_check.enabled`: Enable semantic checking when DB validation fails

## Testing Notes

- Tests use fixtures in `tests/fixtures/project/`
- 98+ test files covering all stages and LLM enhancements
- Run from repository root: `python3 -m pytest -q`
- Unified acceptance: `python3 scripts/ci/release_acceptance.py`
- Individual acceptance tests:
  - `python3 scripts/ci/opencode_smoke_acceptance.py`
  - `python3 scripts/ci/degraded_runtime_acceptance.py`
  - `python3 scripts/ci/report_rebuild_acceptance.py`
- Schema validation before committing: `python3 scripts/schema_validate_all.py`

### V8 Stage Implementation Status

| Stage | Status | Modules |
|-------|--------|---------|
| Discovery | ✅ | Pure Python XML parsing |
| Branching | ✅ | 16 modules |
| Pruning | ⚠️ Partial | Static analysis only |
| Baseline | ⚠️ Partial | Simplified |
| Optimize | ⚠️ Partial | execute_one.py present |
| Validate | ⚠️ Partial | execute_one.py present |
| Patch | ✅ | execute_one.py present |
| Report | ❌ | Not implemented |

### Scanner Coverage Validation

The V8 scanner supports these MyBatis dynamic tags (pure Python implementation):
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
- `tests/fixtures/project/runs/<run_id>/sqlmap_catalog/`

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
- `docs/V8/V8_STAGES_OVERVIEW.md`: V8 seven-stage architecture detailed overview
- `docs/V8/V8_SUMMARY.md`: V8 architecture design summary
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
