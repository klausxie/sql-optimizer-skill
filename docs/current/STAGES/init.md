# Init Stage

**Purpose**: Scan MyBatis XML files, extract SQL units, collect table schemas and field distributions.

## Input

- `sqlopt.yml` configuration file

## Output

| File | Description |
|------|-------------|
| `sql_units.json` | SQL units extracted from XML |
| `sql_fragments.json` | SQL fragment definitions |
| `table_schemas.json` | Database table column/index info |
| `xml_mappings.json` | XML file to SQL unit mappings |
| `field_distributions.json` | WHERE field cardinality stats |
| `SUMMARY.md` | Human-readable summary |

## Key Classes

- `InitStage(Stage[None, InitOutput])`
- `extract_table_schemas()` in `table_extractor.py`
- `extract_field_distributions()` in `table_extractor.py`

## Progress Tracking

Cumulative progress across:
1. File parsing (per-mapper)
2. Schema extraction (per-table)
3. Field distribution (per-field)

See `python/sqlopt/stages/init/stage.py`
