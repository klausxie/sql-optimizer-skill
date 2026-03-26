# Recognition Stage

## Purpose

`recognition` turns SQL branches into baseline evidence.

## Inputs

- parse branch artifacts
- optional table schemas from init
- optional DB connector
- optional LLM provider or mock provider

## Main work

- resolve MyBatis placeholders to sample values
- run `EXPLAIN` or provider-based plan generation
- execute real query baselines for read-only SQL when a DB connector is available
- capture:
  - plan
  - estimated cost
  - actual time
  - rows returned
  - rows examined
  - result signature
  - execution error

## Execution strategy

- estimate-only mode can use bounded concurrency
- real DB baseline mode switches to sequential execution for safer connection handling
- branch-level failures are captured in `execution_error`

## Outputs

- `baselines.json`
- `units/{unit_id}.json`
- `units/_index.json`
- `SUMMARY.md`

## Primary implementation

- `python/sqlopt/stages/recognition/stage.py`
- `python/sqlopt/common/db_connector.py`

## Related docs

- [Recognition contracts](../CONTRACTS/recognition.md)
- [Optimize stage](optimize.md)
