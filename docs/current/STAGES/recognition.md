# Recognition Stage

**Purpose**: Collect EXPLAIN plans, generate performance baselines.

## Input

- `sql_units_with_branches.json` from Parse stage
- `table_schemas.json` from Init stage

## Output

| File | Description |
|------|-------------|
| `baselines.json` | Performance baseline per branch |
| `units/{id}.json` | Per-unit baseline data |
| `SUMMARY.md` | Human-readable summary |

## Baseline Generation

- MockLLMProvider generates realistic baseline data
- Sequential and concurrent execution modes
- MyBatis parameter resolution for EXPLAIN

## Key Classes

- `RecognitionStage(Stage[None, RecognitionOutput])`
- `MockLLMProvider` in `common/llm_mock_generator.py`

See `python/sqlopt/stages/recognition/stage.py`
