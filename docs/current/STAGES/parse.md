# Parse Stage

**Purpose**: Expand dynamic SQL tags (if/include/foreach), generate execution branches.

## Input

- `sql_units.json` from Init stage

## Output

| File | Description |
|------|-------------|
| `sql_units_with_branches.json` | Aggregated index |
| `units/{id}.json` | Per-unit branch data |
| `SUMMARY.md` | Human-readable summary |

## Branch Generation

- `LadderSamplingStrategy`: Generate diverse branch combinations
- `BranchExpander`: Parse XML, expand dynamic tags
- `BranchGenerator`: Generate branch permutations

## Key Classes

- `ParseStage(Stage[None, ParseOutput])`
- `BranchExpander` in `branch_expander.py`
- `LadderSamplingStrategy` in `branching/branch_strategy.py`

See `python/sqlopt/stages/parse/stage.py`
