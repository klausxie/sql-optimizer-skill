# Init Contracts

Source: `python/sqlopt/contracts/init.py`

## Main types

### `SQLUnit`

| Field | Meaning |
| --- | --- |
| `id` | Stable unit ID |
| `mapper_file` | Mapper filename |
| `sql_id` | XML statement ID |
| `sql_text` | Original SQL XML text |
| `statement_type` | `SELECT`, `INSERT`, `UPDATE`, or `DELETE` |

### `SQLFragment`

Reusable `<sql id="...">` fragment extracted from mapper XML.

### `TableSchema`

- columns
- indexes
- statistics such as row count

### `FieldDistribution`

- `table_name`
- `column_name`
- `distinct_count`
- `null_count`
- `total_count`
- `top_values`
- `min_value`
- `max_value`

### `XMLMapping`

Maps extracted statements and fragments back to their original XML files.

### `InitOutput`

Top-level stage output containing:

- `sql_units`
- `run_id`
- `timestamp`
- `sql_fragments`
- `table_schemas`
- `xml_mappings`

## Output files

- `runs/{run_id}/init/sql_units.json`
- `runs/{run_id}/init/sql_fragments.json`
- `runs/{run_id}/init/table_schemas.json`
- `runs/{run_id}/init/field_distributions.json`
- `runs/{run_id}/init/xml_mappings.json`
