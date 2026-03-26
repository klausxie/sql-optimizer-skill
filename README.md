# SQL Optimizer

SQL Optimizer is a MyBatis XML slow-SQL analysis pipeline.

It scans mapper XML files, expands dynamic SQL branches, validates candidates with `EXPLAIN` and optional baseline execution, generates optimization proposals, and produces a final report with ranked findings and optional patches.

## What The Project Does

- Finds SQL statements in MyBatis mapper XML files.
- Expands dynamic SQL branches such as `if`, `choose`, `foreach`, `bind`, and `include`.
- Uses schema, index, row-count, and field-distribution metadata to improve slow-SQL detection.
- Runs `EXPLAIN` and baseline execution when a real MySQL or PostgreSQL test database is available.
- Generates optimization proposals and validates optimized SQL against the same baseline.
- Produces a final ranked report and patch-ready output.

## Pipeline

| Stage | Goal | Main output |
| --- | --- | --- |
| `init` | Scan XML, extract SQL units, schema facts, and field distributions | `runs/{run_id}/init/` |
| `parse` | Expand MyBatis dynamic SQL into executable branches | `runs/{run_id}/parse/` |
| `recognition` | Collect plans and baseline metrics | `runs/{run_id}/recognition/` |
| `optimize` | Generate and validate optimization proposals | `runs/{run_id}/optimize/` |
| `result` | Rank findings and emit report and patches | `runs/{run_id}/result/` |

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Create `sqlopt.yml`

```yaml
config_version: v1
project_root_path: .
scan_mapper_globs:
  - "src/main/resources/**/*.xml"

db_platform: postgresql
db_host: localhost
db_port: 5432
db_name: app
db_user: postgres
db_password: postgres

llm_enabled: false
llm_provider: mock
```

### 3. Run the pipeline

```bash
sqlopt run 1 --config sqlopt.yml
sqlopt run 2 --config sqlopt.yml
sqlopt run 3 --config sqlopt.yml
sqlopt run 4 --config sqlopt.yml
sqlopt run 5 --config sqlopt.yml
```

You can also use stage names:

```bash
sqlopt run init --config sqlopt.yml
sqlopt run parse --config sqlopt.yml
sqlopt run recognition --config sqlopt.yml
sqlopt run optimize --config sqlopt.yml
sqlopt run result --config sqlopt.yml
```

### 4. Inspect outputs

Each run is written to `runs/{run_id}/`.

Important files:

- `runs/{run_id}/init/sql_units.json`
- `runs/{run_id}/init/field_distributions.json`
- `runs/{run_id}/parse/sql_units_with_branches.json`
- `runs/{run_id}/recognition/baselines.json`
- `runs/{run_id}/optimize/proposals.json`
- `runs/{run_id}/result/report.json`

## Real-World Validation

The repository includes a real integration sample project:

- `tests/real/mybatis-test`

Use it to validate the pipeline against MyBatis XML, MySQL, and PostgreSQL test databases.

## Documentation Map

Start here if you are new to the project:

- [Documentation Home](docs/current/README.md)
- [Project Summary](docs/current/SUMMARY.md)
- [Architecture](docs/current/ARCHITECTURE.md)
- [Data Flow](docs/current/DATAFLOW.md)

Stage design:

- [Stage Overview](docs/current/STAGES/README.md)
- [Init Stage](docs/current/STAGES/init.md)
- [Parse Stage](docs/current/STAGES/parse.md)
- [Recognition Stage](docs/current/STAGES/recognition.md)
- [Optimize Stage](docs/current/STAGES/optimize.md)
- [Result Stage](docs/current/STAGES/result.md)

Data contracts:

- [Contracts Overview](docs/current/CONTRACTS/overview.md)
- [Init Contracts](docs/current/CONTRACTS/init.md)
- [Parse Contracts](docs/current/CONTRACTS/parse.md)
- [Recognition Contracts](docs/current/CONTRACTS/recognition.md)
- [Optimize Contracts](docs/current/CONTRACTS/optimize.md)
- [Result Contracts](docs/current/CONTRACTS/result.md)

Supporting modules and historical material:

- [Common Runtime Modules](docs/current/COMMON/overview.md)
- [Archive Index](docs/archive/README.md)
- [Design Decisions](docs/decisions/README.md)

## Testing

```bash
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

For a real project smoke test:

```bash
cd tests/real/mybatis-test
mvn test -q
```

## Current Design Notes

- Large projects are handled with per-unit files in parse, recognition, and optimize stages.
- Safe concurrency is used where it helps, and real DB validation falls back to sequential execution when shared-connection safety matters.
- CLI progress works in both TTY and non-TTY environments and now shows stage percent, throughput, and ETA without flooding logs.

## License

MIT
