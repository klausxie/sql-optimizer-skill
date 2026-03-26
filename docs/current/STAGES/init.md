# Init Stage

**Purpose**: Scan MyBatis XML files, extract SQL units, collect table schemas and field distributions.

## What It Does

1. Scans mapper XML files using glob patterns from config
2. Extracts SQL statements and SQL fragment definitions
3. Connects to DB (if configured) to extract table schemas
4. Collects WHERE clause field cardinality distributions

## Input

- `sqlopt.yml` configuration file

## Output Files

| File | Description |
|------|-------------|
| `sql_units.json` | SQL units extracted from XML (id, mapper_file, sql_id, sql_text, statement_type) |
| `sql_fragments.json` | SQL fragment definitions |
| `table_schemas.json` | Database table column/index info (from DB if configured) |
| `xml_mappings.json` | XML file to SQL unit mappings |
| `field_distributions.json` | WHERE field cardinality stats (top values, distinct count, null count) |
| `SUMMARY.md` | Human-readable summary with actionable insights |

## Key Functions

```python
# stage.py
extract_table_schemas(table_names, db_connector, platform, progress_callback)
extract_field_distributions(table_name, column_names, db_connector, platform, top_n, progress_callback)
```

## Progress Tracking

Cumulative progress across three phases:
1. **File parsing**: (file_idx, total_files) → reports progress per XML file
2. **Schema extraction**: (file_count + schema_idx, total_work) → cumulative across tables
3. **Field distribution**: (file_count + table_count + field_idx, total_work) → cumulative

## Configuration

```yaml
db_platform: postgresql  # or mysql
db_host: localhost
db_port: 5432
db_name: myapp
db_user: postgres
db_password: secret
scan_mapper_globs:
  - "src/main/resources/**/*.xml"
statement_types:  # optional filter
  - SELECT
```

## Stub Mode

When `run_id=None`, returns hardcoded stub data for isolated testing:
- Single SQL unit: `"SELECT * FROM users WHERE id = #{id}"`
- No DB connection required

## See Also

- `python/sqlopt/stages/init/stage.py`
- `python/sqlopt/stages/init/table_extractor.py`
