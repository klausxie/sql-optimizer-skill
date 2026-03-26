# Architecture

## Overview

SQL Optimizer is a MyBatis XML SQL optimization tool with a 5-stage pipeline. It analyzes and optimizes SQL statements extracted from MyBatis mapper XML files.

## Pipeline

```
InitStage → ParseStage → RecognitionStage → OptimizeStage → ResultStage
    │            │              │                │             │
    ▼            ▼              ▼                ▼             ▼
 sql_units   branches      baselines         proposals       report
```

## Directory Structure

```
sqlopt/
├── cli/
│   └── main.py              # CLI: sqlopt run|mock
├── stage_runner.py          # Pipeline orchestrator
├── common/                   # Shared utilities (13 modules)
│   ├── config.py            # SQLOptConfig + load_config()
│   ├── run_paths.py          # RunPaths - run directory management
│   ├── progress.py           # ProgressTracker - stage monitoring
│   ├── progress_display.py   # User-friendly progress bar (TTY/non-TTY)
│   ├── errors.py             # SQLOptError hierarchy (5 types)
│   ├── db_connector.py       # DBConnector - PostgreSQL/MySQL
│   ├── db_pool.py           # DBPoolBase + PostgresPool
│   ├── llm_mock_generator.py # MockLLMProvider for baselines/suggestions
│   ├── mock_data_loader.py   # MockDataLoader - mock-first path resolution
│   ├── concurrent.py         # ConcurrentExecutor for parallel work
│   ├── contract_file_manager.py  # Per-unit JSON file I/O
│   └── summary_generator.py  # SUMMARY.md generation
└── stages/
    ├── base.py              # Stage[T, T] abstract base class
    ├── init/stage.py        # InitStage - XML scanning, SQL extraction
    ├── parse/stage.py       # ParseStage - dynamic tag expansion
    ├── recognition/stage.py # RecognitionStage - baseline collection
    ├── optimize/stage.py    # OptimizeStage - LLM optimization
    ├── result/stage.py      # ResultStage - report and patches
    └── branching/            # Shared branching logic (14 modules)
        ├── branch_generator.py
        ├── branch_strategy.py    # LadderSamplingStrategy
        ├── xml_language_driver.py
        ├── xml_script_builder.py
        ├── fragment_registry.py
        └── ...
```

## Stage Summary

| Stage | Input | Output | Key Classes |
|-------|-------|--------|------------|
| **Init** | None | sql_units, table_schemas, field_distributions | InitStage, table_extractor |
| **Parse** | InitOutput | sql_units_with_branches | ParseStage, BranchExpander |
| **Recognition** | ParseOutput | baselines | RecognitionStage, MockLLMProvider |
| **Optimize** | ParseOutput + RecognitionOutput | proposals | OptimizeStage, MockLLMProvider |
| **Result** | OptimizeOutput | report, patches | ResultStage |

## Key Design Decisions

1. **Single stage.py per stage**: All logic in one file for simplicity
2. **Mock providers**: MockLLMProvider for CI/CD without real DB/LLM
3. **Per-unit files**: Parse/Recognition/Optimize write `units/{id}.json` + `_index.json`
4. **difflib for patches**: Simple unified diff, not structured operations
5. **Cumulative progress**: Progress bar shows continuous progress within each stage

See `../decisions/` for detailed decision records.

## Design Principles

- **Stage autonomy**: Each stage is self-contained, can be tested independently
- **Contract-driven**: Stage communication via JSON files (Python dataclasses with to_json())
- **CI-friendly**: Mock mode for testing without real DB or LLM

See `../archive/v10-refactor-original/` for historical design documents.
