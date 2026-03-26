# Optimize Stage

## Purpose

`optimize` generates rewrite proposals and validates them against the baseline collected in recognition.

## Inputs

- recognition baselines
- table schema metadata
- optional DB connector
- LLM or mock provider

## Main work

- generate optimized SQL proposals
- compare optimized SQL against the original baseline
- collect:
  - before metrics
  - after metrics
  - result equivalence
  - validation status
  - validation error
  - gain ratio

## Validation modes

- `estimated_only`: no real DB connector, compare plan-level metrics only
- `explained_only`: real DB connector available, but query is not safe to execute
- `validated`: optimized SQL executed and matched the baseline signature
- `result_mismatch`: optimized SQL executed but changed the result signature
- `validation_failed`: explain or execution failed

## Concurrency and safety

- estimate-only optimization can run concurrently
- real DB validation switches to sequential mode
- proposal-level failures do not fail the stage; they become validation states

## Outputs

- `proposals.json`
- `units/{unit_id}.json`
- `units/_index.json`
- `SUMMARY.md`

## Primary implementation

- `python/sqlopt/stages/optimize/stage.py`

## Related docs

- [Optimize contracts](../CONTRACTS/optimize.md)
- [Result stage](result.md)
