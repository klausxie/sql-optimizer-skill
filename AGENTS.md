# SQL-OPTIMIZER-SKILL

**Generated:** 2026-03-26
**Language:** Python 3.9+
**Branch:** main

## OVERVIEW

MyBatis XML SQL optimizer with 5-stage pipeline (init → parse → recognition → optimize → result). Analyzes and optimizes SQL statements extracted from MyBatis mapper XML files.

## PIPELINE FLOW

```
InitStage → ParseStage → RecognitionStage → OptimizeStage → ResultStage
    │            │              │                │             │
    ▼            ▼              ▼                ▼             ▼
 sql_units   branches      baselines         proposals       report
```

## STRUCTURE

```
sql-optimizer-skill/
├── python/sqlopt/           # Main package
│   ├── cli/                # CLI entry (sqlopt run/mock)
│   ├── stage_runner.py     # Pipeline orchestrator
│   ├── common/             # Shared utilities (13 modules)
│   ├── contracts/          # Data schemas (6 files)
│   └── stages/             # 5 pipeline stages + branching/
├── tests/
│   ├── unit/              # 26 test files
│   ├── integration/        # Integration tests
│   └── real/mybatis-test/  # Real-world test project
├── docs/
│   ├── current/           # Accurate, up-to-date documentation
│   ├── archive/           # Historical design docs
│   ├── decisions/          # Design decision records
│   └── diagrams/           # Architecture diagrams
├── scripts/               # Build scripts
└── templates/mock/         # Mock data templates
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new stage | `stages/<name>/stage.py` | Inherit `Stage[T, T]` |
| Modify pipeline | `stage_runner.py` | 5-stage orchestration |
| Config loading | `common/config.py` | `SQLOptConfig` dataclass |
| Contract schemas | `contracts/*.py` | Dataclasses with `to_json()` |
| Add LLM provider | `common/llm_mock_generator.py` | `LLMProviderBase` |
| Stage reports | `common/summary_generator.py` | `StageSummary` |
| DB connectors | `common/db_connector.py` | PostgreSQL/MySQL |
| Test a stage | `tests/unit/test_<stage>_stage.py` | Match stage name |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `Stage` | ABC | `stages/base.py` | Base class for all stages |
| `InitStage` | Class | `stages/init/stage.py` | Scans XML, extracts SQL |
| `ParseStage` | Class | `stages/parse/stage.py` | Expands dynamic tags |
| `RecognitionStage` | Class | `stages/recognition/stage.py` | Generates baselines |
| `OptimizeStage` | Class | `stages/optimize/stage.py` | LLM optimization |
| `ResultStage` | Class | `stages/result/stage.py` | Generates report/patches |
| `SQLOptConfig` | Dataclass | `common/config.py` | Main config |
| `MockDataLoader` | Class | `common/mock_data_loader.py` | Mock data loading |
| `ContractFileManager` | Class | `common/contract_file_manager.py` | Per-unit file I/O |
| `ProgressDisplay` | Class | `common/progress_display.py` | User-friendly progress bar |
| `XmlPatchEngine` | Class | `common/xml_patch_engine.py` | Text-based XML patch application |

## STAGE CONTRACTS

| Stage | Input | Output | Output File |
|-------|-------|--------|-------------|
| init | None | `InitOutput` | `runs/{run_id}/init/sql_units.json` |
| parse | `InitOutput` | `ParseOutput` | `runs/{run_id}/parse/units/*.json` |
| recognition | `ParseOutput` | `RecognitionOutput` | `runs/{run_id}/recognition/baselines.json` |
| optimize | `ParseOutput` + `RecognitionOutput` | `OptimizeOutput` | `runs/{run_id}/optimize/proposals.json` |
| result | `OptimizeOutput` | `ResultOutput` | `runs/{run_id}/result/report.json` |

## CORE CONTRACTS

| Contract | Fields | Purpose |
|----------|--------|---------|
| `SQLUnit` | id, mapper_file, sql_id, sql_text, statement_type | Single extracted SQL (mapper_file is relative to project_root) |
| `SQLBranch` | path_id, condition, expanded_sql, is_valid, risk_flags | Dynamic SQL variant |
| `PerformanceBaseline` | sql_unit_id, path_id, plan, estimated_cost, actual_time_ms | EXPLAIN output |
| `OptimizationProposal` | sql_unit_id, path_id, original_sql, optimized_sql, rationale | LLM suggestion |
| `Patch` | sql_unit_id, path_id, original_xml, patched_xml, diff | Per-unit XML patch with unified diff |

## OUTPUT PATTERN

Each stage writes to `runs/{run_id}/{stage}/`:

| Stage | Output Files |
|-------|--------------|
| init | `sql_units.json`, `sql_fragments.json`, `table_schemas.json`, `xml_mappings.json`, `field_distributions.json`, `SUMMARY.md` |
| parse | `units/*.json` + `units/_index.json` |
| recognition | `baselines.json` + `units/*.json` |
| optimize | `proposals.json` + `units/*.json` |
| result | `report.json`, `SUMMARY.md` + `units/*.patch`, `units/*.meta.json`, `units/_index.json` |

Per-unit JSON files managed by `ContractFileManager`.

## COMMON MODULE USAGE HEAT MAP

| Module | init | parse | recognition | optimize | result |
|--------|------|-------|-------------|----------|--------|
| config.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| run_paths.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| progress.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| progress_display.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| errors.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| db_connector.py | ✓ | - | ✓ | - | - |
| db_pool.py | ✓ | - | ✓ | - | - |
| llm_mock_generator.py | - | - | ✓ | ✓ | - |
| mock_data_loader.py | - | ✓ | ✓ | ✓ | ✓ |
| concurrent.py | - | - | ✓ | ✓ | - |
| contract_file_manager.py | - | ✓ | ✓ | ✓ | - |
| summary_generator.py | ✓ | - | - | - | ✓ |

## ANTI-PATTERNS (THIS PROJECT)

| Forbidden | Rule |
|----------|------|
| `except:` (bare) | ERROR-001 |
| `except: pass` | ERROR-002 |
| `eval()` | SECURITY-003 |
| `from X import *` | IMPORT-001 |
| Hardcoded credentials | SECURITY-001 |
| `sys.exit()` in lib | EXIT-001 |

## UNIQUE STYLES

- **Stub pattern**: Stages return stub data when `run_id=None` for isolated testing
- **Per-unit files**: Parse/Recognition/Optimize write `units/{id}.json` + `_index.json`
- **Best-effort SUMMARY**: Report generation failures don't block stage completion
- **progress_display vs progress**: `progress_display.py` = user output, `progress.py` = internal tracking

## COMMANDS

```bash
# Run pipeline
sqlopt run 1          # init
sqlopt run 2          # parse
sqlopt run 3          # recognition
sqlopt run 4          # optimize
sqlopt run 5          # result

# Run with config
sqlopt run 1 --config sqlopt.yml

# Mock data
sqlopt mock <run_id>

# Apply patches
sqlopt apply <unit_id> --run-id <run_id> [--project-root .] [--dry-run]  # Apply patch to mapper XML
sqlopt diff <unit_id> --run-id <run_id>   # Show patch diff
sqlopt patches --run-id <run_id>          # List available patches

# Tests
python -m pytest tests/unit/ -v
```

## TESTING

```bash
python -m pytest tests/unit/test_init_stage.py -v
python -m pytest tests/unit/test_parse_stage.py -v
# Mock mode: set llm_provider: mock in sqlopt.yml
```

## NOTES

- **Lint**: `cd python && ruff check sqlopt/`
- **Pre-commit**: `git config core.hooksPath .claude/lint`
- **Entry point**: `sqlopt = "sqlopt.cli.main:main"` (pyproject.toml)
- **17 Pyright errors** (pre-existing, not blocking)
- **Documentation**: `docs/current/` has accurate, up-to-date docs
- **Design decisions**: `docs/decisions/` has decision records
