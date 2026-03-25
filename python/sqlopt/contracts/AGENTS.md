# CONTRACTS

Type-safe datacontracts for 5-stage pipeline communication.

## STRUCTURE

```
contracts/
├── base.py          # save_json_file(), load_json_file(), dataclass_to_json()
├── init.py          # SQLUnit, SQLFragment, TableSchema, XMLMapping, InitOutput
├── parse.py         # SQLBranch, SQLUnitWithBranches, Risk, ParseOutput
├── recognition.py   # PerformanceBaseline, RecognitionOutput
├── optimize.py      # OptimizationProposal, OptimizeOutput
└── result.py        # Report, Patch, ResultOutput
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new contract | Create in `contracts/` with `to_json()` + `from_json()` |
| JSON serialization | `base.py` |
| Stage I/O mapping | See table below |

## STAGE CONTRACTS

| Stage | Input | Output | Output File |
|-------|-------|--------|-------------|
| init | None | `InitOutput` | `runs/{run_id}/init/sql_units.json` |
| parse | `InitOutput` | `ParseOutput` | `runs/{run_id}/parse/sql_units_with_branches.json` |
| recognition | `ParseOutput` | `RecognitionOutput` | `runs/{run_id}/recognition/baselines.json` |
| optimize | `ParseOutput` + `RecognitionOutput` | `OptimizeOutput` | `runs/{run_id}/optimize/proposals.json` |
| result | `OptimizeOutput` | `ResultOutput` | `runs/{run_id}/result/report.json` |

## CORE CONTRACTS

| Contract | Fields | Purpose |
|----------|--------|---------|
| `SQLUnit` | id, mapper_file, sql_id, sql_text, statement_type | Single extracted SQL |
| `SQLBranch` | path_id, condition, expanded_sql, is_valid, risk_flags | Dynamic SQL variant |
| `PerformanceBaseline` | sql_unit_id, path_id, plan, estimated_cost | EXPLAIN output |
| `OptimizationProposal` | sql_unit_id, path_id, original_sql, optimized_sql, rationale | LLM suggestion |
| `Patch` | sql_unit_id, original_xml, patched_xml, diff | XML diff |

## CONVENTIONS

- All contracts are `@dataclass`
- All have `to_json() -> str` and `from_json(str) -> cls`
- Use `asdict()` for nested serialization
- camelCase for JSON fields (e.g., `fragmentId`, `sqlKey`)

## ANTI-PATTERNS

| Forbidden | Reason |
|-----------|--------|
| `Any` type | Loses type safety |
| Missing `to_json()` | Breaks serialization |
| Adding fields without `from_json()` | Breaks deserialization |
| Mutable defaults without `field()` | Shared state bug |

## USAGE

```python
from sqlopt.contracts import InitOutput, ParseOutput, save_json_file

# Serialize
output = InitOutput(sql_units=[...], run_id="run-123")
save_json_file(output, "runs/run-123/init/sql_units.json")

# Deserialize
data = load_json_file("runs/run-123/init/sql_units.json")
output = InitOutput.from_json(json.dumps(data))
```
