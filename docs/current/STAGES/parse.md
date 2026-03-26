# Parse Stage

## Purpose

`parse` expands MyBatis dynamic SQL into branch-level SQL that can be validated independently.

## Inputs

- `init/sql_units.json`
- `init/sql_fragments.json`
- `init/table_schemas.json`
- `init/field_distributions.json`

## Main work

- resolve local and cross-file `<include>` fragments
- expand `if`, `choose`, `foreach`, `bind`, and related dynamic nodes
- create one or more `SQLBranch` objects per `SQLUnit`
- mark invalid or risky branches
- score branch risk using SQL text, table metadata, and field distributions

## Concurrency and isolation

- concurrent expansion is allowed because SQL units are independent
- work is batched and bounded by the shared concurrent executor
- if one unit fails expansion, the stage emits an `error` branch for that unit and continues

## Outputs

- `sql_units_with_branches.json`
- `units/{unit_id}.json`
- `units/_index.json`
- `SUMMARY.md`

## Primary implementation

- `python/sqlopt/stages/parse/stage.py`
- `python/sqlopt/stages/parse/branch_expander.py`
- `python/sqlopt/stages/branching/`

## Related docs

- [Parse contracts](../CONTRACTS/parse.md)
- [Recognition stage](recognition.md)
