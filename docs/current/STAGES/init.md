# Init Stage

## Purpose

`init` converts mapper XML files into stable SQL units and metadata that later stages can reuse.

## Inputs

- project root
- mapper glob patterns
- optional MySQL or PostgreSQL connection

## Main work

- find mapper XML files
- parse statements and reusable SQL fragments
- create `SQLUnit` records
- build XML mappings back to the original files
- extract referenced table names
- extract predicate field names by table
- load table schema and index metadata
- load field distributions for predicate columns

## Outputs

- `sql_units.json`
- `sql_fragments.json`
- `table_schemas.json`
- `field_distributions.json`
- `xml_mappings.json`
- `SUMMARY.md`

## Large-project and failure behavior

- mapper files that fail parsing are skipped instead of aborting the whole stage
- field distribution extraction only runs for columns that are confirmed to exist in the extracted schema
- metadata is written once and reused by later stages

## Primary implementation

- `python/sqlopt/stages/init/stage.py`
- `python/sqlopt/stages/init/parser.py`
- `python/sqlopt/stages/init/table_extractor.py`

## Related docs

- [Init contracts](../CONTRACTS/init.md)
- [Data Flow](../DATAFLOW.md)
