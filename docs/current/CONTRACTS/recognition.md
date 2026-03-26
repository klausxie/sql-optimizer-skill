# Recognition Contracts

Source: `python/sqlopt/contracts/recognition.py`

## Main types

### `PerformanceBaseline`

| Field | Meaning |
| --- | --- |
| `sql_unit_id` | Upstream SQL unit ID |
| `path_id` | Upstream branch ID |
| `original_sql` | Expanded SQL before optimization |
| `plan` | Parsed `EXPLAIN` plan |
| `estimated_cost` | Planner or provider cost estimate |
| `actual_time_ms` | Measured execution time when available |
| `rows_returned` | Returned row count when query execution is allowed |
| `rows_examined` | Best-effort examined row count |
| `result_signature` | Stable checksum summary of query results |
| `execution_error` | Plan or execution error captured at branch level |
| `branch_type` | Branch mode propagated from parse |

### `RecognitionOutput`

Top-level list of baselines.

## Output files

- `runs/{run_id}/recognition/baselines.json`
- `runs/{run_id}/recognition/units/{unit_id}.json`
- `runs/{run_id}/recognition/units/_index.json`
