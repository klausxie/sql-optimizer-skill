# Result Contracts

Source: `python/sqlopt/contracts/result.py`

## Main types

### `Report`

Human-readable result summary:

- `summary`
- `details`
- `risks`
- `recommendations`

### `Patch`

| Field | Meaning |
| --- | --- |
| `sql_unit_id` | SQL unit being patched |
| `original_xml` | Original XML text |
| `patched_xml` | Replacement XML text |
| `diff` | Unified diff |

### `ResultOutput`

Top-level result payload:

- `can_patch`
- `report`
- `patches`

## Output files

- `runs/{run_id}/result/report.json`
- `runs/{run_id}/result/SUMMARY.md`
