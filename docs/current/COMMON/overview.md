# Common Runtime Modules

These modules are shared across multiple stages and define the runtime behavior of the pipeline.

## Core modules

| Module | Responsibility |
| --- | --- |
| `common/config.py` | Loads `SQLOptConfig` and concurrency settings |
| `common/run_paths.py` | Resolves canonical run output paths |
| `common/progress.py` | Tracks stage status and timestamps |
| `common/progress_display.py` | CLI progress rendering for TTY and non-TTY runs |
| `common/concurrent.py` | Batched, bounded, retry-capable task execution |
| `common/db_connector.py` | MySQL and PostgreSQL plan/query execution |
| `common/contract_file_manager.py` | Per-unit JSON read/write helpers |
| `common/mock_data_loader.py` | Mock-first path resolution used in tests and local development |
| `common/summary_generator.py` | `SUMMARY.md` generation helpers |

## Important runtime rules

- Run artifacts live under `runs/{run_id}/`.
- Parse, recognition, and optimize stages support per-unit outputs.
- Real DB validation uses the DB connector directly and falls back to sequential execution where connection safety matters.
- Progress output is human-readable even when the command runs in CI logs or redirected stdout.

## Related docs

- [Architecture](../ARCHITECTURE.md)
- [Data Flow](../DATAFLOW.md)
- [Contracts](../CONTRACTS/overview.md)
