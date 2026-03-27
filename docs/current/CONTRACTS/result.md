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
| `diff` | Unified diff with header `a/{filename}` / `b/{filename}` (filename only, not full path) |

### `ResultOutput`

Top-level result payload:

- `can_patch`
- `report`
- `patches`

## Output files

- `runs/{run_id}/result/report.json`
- `runs/{run_id}/result/SUMMARY.md`
- `runs/{run_id}/result/units/_index.json` — list of unit IDs with patches
- `runs/{run_id}/result/units/{unit_id}.patch` — unified diff patch file
- `runs/{run_id}/result/units/{unit_id}.meta.json` — patch metadata (operation, confidence, rationale, snippets)

### Per-unit patch metadata

Each `.meta.json` file contains:

| Field | Meaning |
| --- | --- |
| `sql_unit_id` | SQL unit identifier |
| `sql_id` | XML statement ID |
| `mapper_file` | Relative path to mapper file |
| `operation` | Patch operation: `ADD`, `REPLACE`, `REMOVE`, `WRAP` |
| `confidence` | LLM confidence score |
| `rationale` | Optimization rationale |
| `original_snippet` | Original code fragment (null for ADD) |
| `rewritten_snippet` | Replacement code fragment |
| `issue_type` | Issue category (e.g. `MISSING_LIMIT`, `TYPE_MISMATCH`) |
