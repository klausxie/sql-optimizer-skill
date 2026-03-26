# Parse Stage

**Purpose**: Expand dynamic SQL tags (if/include/foreach), generate execution branch combinations.

## What It Does

1. Loads SQL units from Init stage output
2. Parses MyBatis XML SQL using XMLLanguageDriver
3. Generates branch combinations using BranchGenerator with LadderSamplingStrategy
4. Writes per-unit branch data to `units/{id}.json`

## Input

- `sql_units.json` from Init stage

## Output Files

| File | Description |
|------|-------------|
| `sql_units_with_branches.json` | Aggregated index of all units with branches |
| `units/{id}.json` | Per-unit branch data |
| `SUMMARY.md` | Human-readable summary |

## Branch Generation

### LadderSamplingStrategy

Generates diverse branch combinations by exploring different condition combinations:

```
For a SQL with 3 <if> tags:
- Branch 1: all conditions true
- Branch 2: condition 1 false, 2+3 true
- Branch 3: condition 2 false, 1+3 true
- ...
```

### Risk Scoring

Each branch gets a risk score based on:
- SQL complexity (subquery depth, JOIN count)
- Data distribution (from field_distributions)
- Unbalanced conditions

## Key Classes

```python
# branch_expander.py
class BranchExpander:
    def expand(sql_text, default_namespace) -> List[ExpandedBranch]

# branching/branch_strategy.py
class LadderSamplingStrategy:
    def generate(sql_node) -> List[BranchDict]
```

## Configuration

```yaml
parse_strategy: ladder    # sampling strategy
parse_max_branches: 50   # max branches per SQL unit
```

## Per-Unit Format

Parse/Recognition/Optimize all use per-unit files:

```
runs/{run_id}/parse/
├── sql_units_with_branches.json   # aggregated index
└── units/
    ├── unit-1.json               # branches for unit-1
    ├── unit-2.json
    └── _index.json               # index of all units
```

## Stub Mode

When `run_id=None`, returns stub data with single default branch.

## See Also

- `python/sqlopt/stages/parse/stage.py`
- `python/sqlopt/stages/parse/branch_expander.py`
- `python/sqlopt/stages/branching/branch_strategy.py`
