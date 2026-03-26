# Result Stage

## Purpose

`result` turns proposals and baselines into a ranked report and optional patch set.

## Inputs

- init SQL units
- recognition baselines
- optimize proposals

## Main work

- rank proposals by validated impact
- separate:
  - verified improvements
  - candidates that still need validation
  - result mismatches
  - validation failures
- generate patches only for proposals that are safe enough to patch
- generate a summary report for humans

## Patch generation rule

A proposal is patch-ready only when:

- validation status is `validated`
- result equivalence is not false
- gain ratio is not negative

## Outputs

- `report.json`
- `SUMMARY.md`

## Primary implementation

- `python/sqlopt/stages/result/stage.py`

## Related docs

- [Result contracts](../CONTRACTS/result.md)
- [Data Flow](../DATAFLOW.md)
