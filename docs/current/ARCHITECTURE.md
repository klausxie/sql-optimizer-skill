# Architecture

## System overview

The implementation is a file-based pipeline orchestrated by `StageRunner`.

```text
InitStage -> ParseStage -> RecognitionStage -> OptimizeStage -> ResultStage
   |             |                |                  |                |
   v             v                v                  v                v
 sql_units    branches         baselines         proposals          report
```

The pipeline persists stage outputs under `runs/{run_id}/` and allows later stages to resume from disk.

## Main building blocks

### Stage runner

- `python/sqlopt/stage_runner.py`
- Loads config.
- Creates the run directory layout.
- Wires DB connectors and LLM providers.
- Drives stage-by-stage execution and CLI progress output.

### Stage modules

- `python/sqlopt/stages/init/`
- `python/sqlopt/stages/parse/`
- `python/sqlopt/stages/recognition/`
- `python/sqlopt/stages/optimize/`
- `python/sqlopt/stages/result/`

Each stage reads the previous stage's persisted artifacts, transforms them, and writes its own outputs.

### Shared runtime modules

- `common/config.py`
- `common/run_paths.py`
- `common/progress.py`
- `common/progress_display.py`
- `common/concurrent.py`
- `common/db_connector.py`
- `common/contract_file_manager.py`
- `common/mock_data_loader.py`
- `common/xml_patch_engine.py`

## Large-project design

The current implementation uses several tactics to stay usable on larger mapper sets.

### Per-unit outputs

Parse, recognition, and optimize stages write:

- one compatibility file for the whole stage
- one `units/{unit_id}.json` file per SQL unit
- one `_index.json` file for unit discovery

This avoids forcing downstream tools to parse one giant JSON blob for all SQL units.

### Safe concurrency

`common/concurrent.py` now supports:

- bounded worker count
- bounded in-flight task count
- batch execution
- retry with exponential backoff
- timeout-based failure classification
- result ordering aligned with input order

### Stage-specific concurrency choices

- `parse` can expand SQL units concurrently because units are independent.
- `recognition` can run concurrently when no real DB connector is used.
- `recognition` switches to sequential mode when real DB baseline execution is active, because plan/query execution should not poison shared connections.
- `optimize` can run concurrently in estimate-only mode and switches to sequential mode when real DB validation is enabled.

## Error-handling model

The project is designed to degrade at the smallest useful scope.

### Pipeline level

- A stage failure fails the current command.
- Completed earlier stages are preserved on disk.

### Stage level

- Summary generation is best-effort and does not block stage completion.
- Real DB connector failures are captured per branch or per proposal where possible.

### Unit level

- `init` skips mapper files that cannot be parsed and continues with the rest.
- `parse` isolates unit-level branch expansion failures and emits an `error` branch instead of aborting the stage.
- `recognition` stores `execution_error` on the baseline when a branch fails plan generation or execution.
- `optimize` stores `validation_status` and `validation_error` instead of failing the whole stage when an optimized SQL validation fails.

## Progress reporting

The CLI now provides stage progress in both TTY and non-TTY environments.

- TTY mode updates the current line in place.
- Non-TTY mode emits throttled snapshots instead of logging every tiny update.
- Progress lines include stage percent, sub-progress, elapsed time, throughput, and ETA.
- Pipeline start and end banners are printed around `run_all()`.

## Patch system

The result stage generates per-unit Git Patch files that can be applied to mapper XML using standard `patch` command or the `sqlopt apply` CLI.

### Patch workflow

1. `ResultStage._create_patch()` generates unified diff from original and patched XML
2. `XmlPatchEngine.apply_text_replacement()` handles structured operations (ADD, REPLACE, REMOVE, WRAP)
3. Per-unit `.patch` and `.meta.json` files are written to `runs/{run_id}/result/units/`
4. `sqlopt apply` validates and applies patches using `patch -d {mapper_dir} -p1`

### Key design decisions

- Diff headers use filename only (`a/TestMapper.xml`) to work with `patch -d {dir}`
- `mapper_file` in contracts stores relative path from project_root
- Patch application creates `.orig` backup files

## Canonical references

- [Data Flow](DATAFLOW.md)
- [Stage design](STAGES/README.md)
- [Contracts](CONTRACTS/overview.md)
