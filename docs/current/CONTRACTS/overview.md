# Data Contracts

## Overview

Python dataclasses with `to_json()` / `from_json()` methods.

## Contracts

| File | Description |
|------|-------------|
| `base.py` | Base dataclass with to_dict/from_dict |
| `init.py` | InitOutput, SQLUnit, SQLFragment, TableSchema, FieldDistribution |
| `parse.py` | ParseOutput, SQLBranch, SQLUnitWithBranches |
| `recognition.py` | RecognitionOutput, PerformanceBaseline |
| `optimize.py` | OptimizeOutput, OptimizationProposal |
| `result.py` | ResultOutput, Report, Patch |

## SQLUnit Fields

```python
id: str           # SQL key (e.g., "findUser")
mapper_file: str  # XML file path
sql_id: str       # Statement ID in XML
sql_text: str     # SQL content
statement_type: str  # SELECT/INSERT/UPDATE/DELETE
```

## Per-Stage Output

Each stage writes to `runs/{run_id}/{stage}/`:
- **init**: `sql_units.json`, `sql_fragments.json`, `table_schemas.json`
- **parse**: `sql_units_with_branches.json`, `units/{id}.json`
- **recognition**: `baselines.json`, `units/{id}.json`
- **optimize**: `proposals.json`, `units/{id}.json`
- **result**: `report.json`, `patches/`

## Validation

No JSON Schema enforcement. Contracts are Python dataclasses validated at runtime.
