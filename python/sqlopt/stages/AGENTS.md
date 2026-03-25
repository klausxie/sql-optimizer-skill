# Stages Module

## STRUCTURE

```
stages/
├── base.py              # Stage[Input, Output] abstract base
├── init/stage.py        # InitStage - scans XML, extracts SQL
├── parse/stage.py       # ParseStage - expands dynamic tags
├── recognition/stage.py # RecognitionStage - generates baselines
├── optimize/stage.py    # OptimizeStage - LLM optimization
├── result/stage.py      # ResultStage - generates report
└── branching/           # Shared branching logic (14 modules)
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new stage | Create `stages/<name>/stage.py` inheriting `Stage[Input, Output]` |
| Stage base class | `base.py` - `timed_run()` context, `validate_input/output()` hooks |
| Branching logic | `branching/` - shared by parse + optimize stages |
| Branch generation | `branching/branch_generator.py` + `branch_strategy.py` |
| XML expansion | `branching/xml_language_driver.py` + `xml_script_builder.py` |

## CODE MAP

| Symbol | Location | Role |
|--------|----------|------|
| `Stage` | `base.py` | Abstract base with timing, validation hooks |
| `InitStage` | `init/stage.py` | Scans MyBatis XML, extracts SQL units |
| `ParseStage` | `parse/stage.py` | Expands if/include/foreach, generates branches |
| `RecognitionStage` | `recognition/stage.py` | Collects EXPLAIN plans, builds baselines |
| `OptimizeStage` | `optimize/stage.py` | Rule-based + LLM optimization proposals |
| `ResultStage` | `result/stage.py` | Aggregates proposals into report/patches |

## CONVENTIONS

- All stages inherit `Stage[Input, Output]` from `base.py`
- Constructor: `super().__init__("stage_name")`
- `run(input_data: Input) -> Output` abstract method
- Stub fallback when `run_id=None` for isolated testing
- Stub data uses hardcoded IDs like `"stub-1"`

## OUTPUT PATTERN

Each stage writes to `runs/{run_id}/{stage}/`:

| Stage | Output Files |
|-------|--------------|
| init | `sql_units.json` |
| parse | `sql_units_with_branches.json` + `units/*.json` |
| recognition | `baselines.json` + `units/*.json` |
| optimize | `proposals.json` + `units/*.json` |
| result | `report.json` |

Per-unit JSON files managed by `ContractFileManager`.

## TESTING

```bash
python -m pytest tests/unit/test_init_stage.py -v
python -m pytest tests/unit/test_parse_stage.py -v
# Mock mode: set llm_provider: mock in sqlopt.yml
```
