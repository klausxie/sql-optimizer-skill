# SQL-OPTIMIZER-SKILL

**Generated:** 2026-03-25
**Language:** Python 3.9+
**Branch:** main

## OVERVIEW

MyBatis XML SQL optimizer with 5-stage pipeline (init → parse → recognition → optimize → result). Analyzes and optimizes SQL statements extracted from MyBatis mapper XML files.

## STRUCTURE

```
sql-optimizer-skill/
├── python/sqlopt/           # Main package
│   ├── cli/                # CLI entry (sqlopt run/mock)
│   ├── stage_runner.py     # Pipeline orchestrator
│   ├── common/             # Shared utilities (12 modules)
│   ├── contracts/          # Data schemas (7 files)
│   └── stages/             # 5 pipeline stages + branching/
├── tests/
│   ├── unit/              # 26 test files
│   ├── integration/        # Integration tests
│   └── real/mybatis-test/  # Real-world test project
├── docs/v10-refactor/      # Architecture docs
├── scripts/                # Build scripts
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

## CONVENTIONS

- **CLI**: `sqlopt run <1-5|name>` or `sqlopt mock <run_id>`
- **Stages**: Type-safe contracts between stages (dataclasses with `to_json()`)
- **Reports**: All SUMMARY.md use Chinese (as of v10)
- **Mock**: `MockDataLoader` intercepts file reads for debugging
- **Error handling**: Unified `SQLOptError` hierarchy

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

# Tests
python -m pytest tests/unit/ -v
```

## NOTES

- **Lint**: `cd python && ruff check sqlopt/`
- **Pre-commit**: `git config core.hooksPath .claude/lint`
- **Entry point**: `sqlopt = "sqlopt.cli.main:main"` (pyproject.toml)
- **17 Pyright errors** (pre-existing, not blocking)
