# sqlopt Package Root

## OVERVIEW

MyBatis XML SQL optimizer with 5-stage pipeline. Entry point via `cli/main.py` or `stage_runner.py`.

## STRUCTURE

```
sqlopt/
├── __init__.py           # Re-exports public API
├── cli/
│   └── main.py           # CLI entry: sqlopt run|mock
├── stage_runner.py       # Pipeline orchestrator (5 stages)
├── stages/               # 5 pipeline stages
├── common/               # Shared utilities (12 modules)
└── contracts/             # Data schemas (7 files)
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| CLI entry point | `cli/main.py` - argparse, subcommands |
| Pipeline orchestration | `stage_runner.py` - stage sequencing |
| Package public API | `__init__.py` - re-exports from submodules |

## CLI USAGE

```bash
# Run pipeline stages
sqlopt run 1          # init
sqlopt run 2          # parse
sqlopt run 3          # recognition
sqlopt run 4          # optimize
sqlopt run 5          # result

# Or by name
sqlopt run init
sqlopt run parse
sqlopt run recognition
sqlopt run optimize
sqlopt run result

# Mock data
sqlopt mock <run_id>

# With config
sqlopt run 1 --config sqlopt.yml
```

## PIPELINE FLOW

```
InitStage → ParseStage → RecognitionStage → OptimizeStage → ResultStage
    │            │              │                │             │
    ▼            ▼              ▼                ▼             ▼
 sql_units   branches      baselines         proposals      report
```

## KEY FILES

| File | Role |
|------|------|
| `cli/main.py` | Argparse CLI, `run` and `mock` subcommands |
| `stage_runner.py` | Orchestrates 5 stages, handles errors, writes SUMMARY.md |
| `__init__.py` | Public API exports |

## CONVENTIONS

- Package uses absolute imports (`from sqlopt.common import ...`)
- CLI entry point: `sqlopt = "sqlopt.cli.main:main"` (pyproject.toml)
- All stage output written to `runs/{run_id}/{stage}/`
- Mock data intercepted via `MockDataLoader` when `mock/` subdir exists
