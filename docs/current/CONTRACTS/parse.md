# Parse Contracts

Source: `python/sqlopt/contracts/parse.py`

## Main types

### `SQLBranch`

| Field | Meaning |
| --- | --- |
| `path_id` | Branch identity inside a SQL unit |
| `condition` | Human-readable condition summary |
| `expanded_sql` | Expanded SQL text |
| `is_valid` | Whether the branch is executable and structurally valid |
| `risk_flags` | Rule-level risk markers |
| `active_conditions` | Conditions active in this branch |
| `risk_score` | Aggregate branch risk score |
| `score_reasons` | Explanations behind the score |
| `branch_type` | Special branch mode such as `baseline_only` or `error` |

### `SQLUnitWithBranches`

Groups all branches belonging to one `sql_unit_id`.

### `ParseOutput`

Top-level list of `SQLUnitWithBranches`.

## Output files

- `runs/{run_id}/parse/sql_units_with_branches.json`
- `runs/{run_id}/parse/units/{unit_id}.json`
- `runs/{run_id}/parse/units/_index.json`
