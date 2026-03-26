# Common IDs And Status Fields

The following identifiers link artifacts across stages.

## Stable IDs

| Field | Meaning |
| --- | --- |
| `run_id` | The pipeline execution identifier under `runs/{run_id}` |
| `sql_unit_id` | Stable statement identity, usually `{namespace}.{statement_id}` |
| `path_id` | Branch identity within one SQL unit |

## Common metric fields

These fields appear in recognition and optimize outputs:

- `estimated_cost`
- `actual_time_ms`
- `rows_returned`
- `rows_examined`
- `result_signature`
- `execution_error`

## Validation-related fields

These fields appear on optimization proposals:

- `validation_status`
- `validation_error`
- `result_equivalent`
- `gain_ratio`
