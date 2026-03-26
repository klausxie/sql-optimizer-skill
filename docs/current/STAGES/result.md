# Result Stage

**Purpose**: Generate reports, create SQL patches.

## Input

- `proposals.json` from Optimize stage
- `baselines.json` from Recognition stage

## Output

| File | Description |
|------|-------------|
| `report.json` | Optimization report |
| `patches/` | Generated SQL patches |
| `SUMMARY.md` | Human-readable summary |

## Report

- Summary with key metrics
- Per-unit recommendations
- Risk assessment

## Patch

Uses `difflib.unified_diff()` to generate unified diff text for SQL changes.

## Key Classes

- `ResultStage(Stage[None, ResultOutput])`

See `python/sqlopt/stages/result/stage.py`
