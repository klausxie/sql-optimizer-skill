# Result Stage

**Purpose**: Generate optimization reports, create SQL patches with unified diffs.

## What It Does

1. Loads proposals from Optimize stage
2. Loads baselines from Recognition stage
3. Generates human-readable report with recommendations
4. Creates SQL patches via `difflib.unified_diff()`

## Input

- `proposals.json` from Optimize stage
- `baselines.json` from Recognition stage

## Output Files

| File | Description |
|------|-------------|
| `report.json` | Full optimization report with summary, details, risks |
| `patches/` | Generated SQL patches (unified diff format) |
| `SUMMARY.md` | Human-readable summary |

## Report Structure

```json
{
  "summary": {
    "total_units": 10,
    "total_proposals": 25,
    "high_confidence": 18,
    "estimated_improvement": "30%"
  },
  "details": [
    {
      "sql_unit_id": "findUser",
      "proposals": [
        {
          "path_id": "default",
          "rationale": "Use covering index",
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

## Patch Generation

Uses Python's `difflib.unified_diff()` to generate unified diff text:

```python
# _create_patch() in result/stage.py
diff = difflib.unified_diff(
    original_sql.splitlines(keepends=True),
    optimized_sql.splitlines(keepends=True),
    fromfile='original.sql',
    tofile='optimized.sql'
)
```

Note: This generates plain diff text, NOT structured REPLACE/ADD/REMOVE/WRAP operations.

## Stub Mode

When `run_id=None`, generates stub report.

## See Also

- `python/sqlopt/stages/result/stage.py`
