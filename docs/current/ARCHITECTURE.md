# ARCHITECTURE

## Overview

SQL Optimizer is a MyBatis XML SQL optimization tool with a 5-stage pipeline.

## Pipeline

```
Init → Parse → Recognition → Optimize → Result
  │        │          │            │        │
  ▼        ▼          ▼            ▼        ▼
sql_units  branches  baselines    proposals  report
```

## Directory Structure

```
sqlopt/
├── cli/
│   └── main.py          # CLI entry: sqlopt run|mock
├── stage_runner.py      # Pipeline orchestrator (5 stages)
├── common/              # Shared utilities
│   ├── config.py        # SQLOptConfig dataclass
│   ├── db_connector.py  # PostgreSQL/MySQL connectors
│   ├── llm_mock_generator.py  # Mock LLM provider
│   ├── progress.py      # Progress tracking
│   ├── progress_display.py   # User-friendly progress display
│   ├── contract_file_manager.py  # Per-unit file I/O
│   └── summary_generator.py   # SUMMARY.md generation
└── stages/
    ├── base.py         # Stage[T, T] abstract base class
    ├── init/stage.py   # InitStage
    ├── parse/stage.py  # ParseStage
    ├── recognition/stage.py  # RecognitionStage
    ├── optimize/stage.py     # OptimizeStage
    └── result/stage.py      # ResultStage
```

## Key Design Decisions

1. **Single stage.py per stage**: All logic in one file for simplicity
2. **Mock providers**: MockLLMProvider for CI/CD without real DB/LLM
3. **Per-unit files**: `units/{id}.json` for granular access
4. **difflib for patches**: Simple unified diff, not structured operations

See `../decisions/` for detailed decision records.
