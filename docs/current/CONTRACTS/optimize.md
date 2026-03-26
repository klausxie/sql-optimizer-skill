# Optimize Contracts

Source: `python/sqlopt/contracts/optimize.py`

## Main types

### `OptimizationProposal`

| Field | Meaning |
| --- | --- |
| `sql_unit_id` | Upstream SQL unit ID |
| `path_id` | Upstream branch ID |
| `original_sql` | SQL before optimization |
| `optimized_sql` | Proposed optimized SQL |
| `rationale` | Explanation of the rewrite |
| `confidence` | Proposal confidence from the provider |
| `before_metrics` | Baseline metrics captured before optimization |
| `after_metrics` | Metrics collected for optimized SQL |
| `result_equivalent` | Whether baseline and optimized signatures match |
| `validation_status` | Validation outcome |
| `validation_error` | Validation failure detail |
| `gain_ratio` | Relative improvement estimate |

### `OptimizeOutput`

Top-level list of proposals.

## Output files

- `runs/{run_id}/optimize/proposals.json`
- `runs/{run_id}/optimize/units/{unit_id}.json`
- `runs/{run_id}/optimize/units/_index.json`
