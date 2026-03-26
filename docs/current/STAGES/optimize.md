# Optimize Stage

**Purpose**: Generate SQL optimization proposals via rules + LLM.

## Input

- `baselines.json` from Recognition stage
- `sql_units_with_branches.json` from Parse stage

## Output

| File | Description |
|------|-------------|
| `proposals.json` | Optimization proposals |
| `units/{id}.json` | Per-unit proposals |
| `SUMMARY.md` | Human-readable summary |

## Optimization

- **Rule-based**: Pattern detection without LLM
- **LLM-based**: MockLLMProvider generates suggestions
- Sequential and concurrent execution

## Key Classes

- `OptimizeStage(Stage[None, OptimizeOutput])`
- `MockLLMProvider` in `common/llm_mock_generator.py`

See `python/sqlopt/stages/optimize/stage.py`
