# Recognition Stage

**Purpose**: Collect EXPLAIN plans, generate performance baselines for each SQL branch.

## What It Does

1. Loads branch data from Parse stage output
2. Resolves MyBatis parameters for EXPLAIN queries
3. Generates baseline performance data via MockLLMProvider
4. Runs sequentially or concurrently based on config

## Input

- `sql_units_with_branches.json` from Parse stage
- `table_schemas.json` from Init stage

## Output Files

| File | Description |
|------|-------------|
| `baselines.json` | Performance baseline per branch (plan, estimated_cost, actual_time_ms) |
| `units/{id}.json` | Per-unit baseline data |
| `SUMMARY.md` | Human-readable summary |

## Baseline Data

```json
{
  "sql_unit_id": "findUser",
  "path_id": "default",
  "original_sql": "SELECT * FROM users WHERE id = ?",
  "plan": "...EXPLAIN output...",
  "estimated_cost": 100.5,
  "actual_time_ms": 15.2
}
```

## Execution Modes

- **Sequential**: `_run_sequential()` - process units one by one
- **Concurrent**: `_run_concurrent()` - process multiple units in parallel via ConcurrentExecutor

## MyBatis Parameter Resolution

Converts MyBatis parameter syntax to SQL:
- `#{id}` → `?` (for EXPLAIN)
- ` ${column}` → resolved column name

## Key Classes

```python
# recognition/stage.py
class RecognitionStage(Stage[None, RecognitionOutput])
class MockLLMProvider:  # common/llm_mock_generator.py
    def generate_baseline(sql: str, platform: str) -> PerformanceBaseline
```

## Configuration

```yaml
concurrency:
  max_workers: 4
  enabled: true
```

## Stub Mode

When `run_id=None`, returns stub baseline data.

## See Also

- `python/sqlopt/stages/recognition/stage.py`
- `python/sqlopt/common/llm_mock_generator.py`
