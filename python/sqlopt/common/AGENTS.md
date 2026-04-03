# SQL-OPTIMIZER-SKILL / COMMON

**Generated:** 2026-04-03
**Language:** Python 3.9+
**Branch:** main

## OVERVIEW

Shared utilities (13 modules, ~3K lines core) used by ALL 5 pipeline stages. Provides configuration, database connectors, LLM providers, concurrency, progress tracking, and file management.

## STRUCTURE

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | 139 | `SQLOptConfig` dataclass + `load_config()` from YAML |
| `db_connector.py` | 402 | `DBConnector` ABC + PostgreSQL/MySQL implementations with `execute_explain()` |
| `llm_mock_generator.py` | 991 | `LLMProviderBase`, `MockLLMProvider`, `OpenAILLMProvider`, `OpenCodeRunLLMProvider` |
| `xml_patch_engine.py` | 390 | `XmlPatchEngine` applying `OptimizationAction[]` to MyBatis XML via ET |
| `summary_generator.py` | 788 | `StageSummary`, `generate_*_summary_markdown()` for all stages |
| `contract_file_manager.py` | 131 | Per-unit file I/O: `runs/{run_id}/{stage}/units/{id}.json` |
| `run_paths.py` | 269 | `RunPaths` for all stage directories and mock paths |
| `progress.py` | 203 | `ProgressTracker` with `StageProgress` dataclass, JSON serialization |
| `progress_display.py` | 189 | `ProgressDisplay` - TTY/in-place and non-TTY periodic output |
| `concurrent.py` | 149 | `ConcurrentExecutor` with `TaskResult`, `BatchOptions`, retry logic |
| `errors.py` | 43 | `SQLOptError` hierarchy: ConfigError, StageError, ContractError, LLMError, DBError |
| `defaults.py` | 25 | `DEFAULT_MAX_BRANCHES=100`, `MAX_CAP=1000` |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add config field | `config.py` - add to `SQLOptConfig` dataclass |
| New LLM provider | `llm_mock_generator.py` - implement `LLMProviderBase` |
| XML patch logic | `xml_patch_engine.py` - `apply_actions()`, `apply_text_replacement()` |
| Change run directory structure | `run_paths.py` - `RunPaths` class |
| Per-unit file pattern | `contract_file_manager.py` - `ContractFileManager` |

## CONVENTIONS

**Imports:** Always absolute imports
```python
from sqlopt.common.run_paths import RunPaths  # CORRECT
from .run_paths import RunPaths                # WRONG
```

**Error handling:** All exceptions inherit from `SQLOptError` with `to_dict()` for JSON serialization.

**Concurrency:** Use `ConcurrentExecutor` with `BatchOptions` for parallel work. Never use bare `except:`.

**Per-unit files:** Parse/Recognition/Optimize write `units/{id}.json` + `_index.json` managed by `ContractFileManager`.

## ANTI-PATTERNS (THIS DIR)

| Forbidden | Rule |
|-----------|------|
| `sys.exit()` in lib | EXIT-001 - Raise exceptions instead |
| `except:` (bare) | ERROR-001 - Catch specific exceptions |
| Relative imports | IMPORT-001 - Use `from sqlopt.X import` |
