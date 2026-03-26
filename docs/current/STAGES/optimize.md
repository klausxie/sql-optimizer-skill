# Optimize Stage

**Purpose**: Generate SQL optimization proposals via LLM analysis of baseline data.

## What It Does

1. Loads baseline data from Recognition stage
2. Analyzes each SQL branch for optimization opportunities
3. Generates proposals via MockLLMProvider
4. Runs sequentially or concurrently based on config

## Input

- `baselines.json` from Recognition stage
- `sql_units_with_branches.json` from Parse stage

## Output Files

| File | Description |
|------|-------------|
| `proposals.json` | Optimization proposals per branch |
| `units/{id}.json` | Per-unit proposals |
| `SUMMARY.md` | Human-readable summary |

## Optimization Proposal

```json
{
  "sql_unit_id": "findUser",
  "path_id": "default",
  "original_sql": "SELECT * FROM users WHERE id = ?",
  "optimized_sql": "SELECT id, name, email FROM users WHERE id = ?",
  "rationale": "Use covering index, reduce data transfer",
  "confidence": 0.85
}
```

## Optimization Types

- **Index suggestion**: Add covering index for WHERE clause
- **Query rewrite**: Use EXISTS instead of IN, avoid SELECT *
- **Limit pushdown**: Move LIMIT to subquery when possible

## Execution Modes

- **Sequential**: `_run_sequential()` - process units one by one
- **Concurrent**: `_run_concurrent()` - process multiple units in parallel

## Key Classes

```python
# optimize/stage.py
class OptimizeStage(Stage[None, OptimizeOutput])

# common/llm_mock_generator.py
class MockLLMProvider:
    def generate_optimization(sql: str, platform: str) -> OptimizationProposal
```

## Configuration

```yaml
concurrency:
  max_workers: 4
  enabled: true
llm_provider: mock
llm_enabled: true
```

## Stub Mode

When `run_id=None`, returns stub optimization proposals.

## See Also

- `python/sqlopt/stages/optimize/stage.py`
- `python/sqlopt/common/llm_mock_generator.py`
