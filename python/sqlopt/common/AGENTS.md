# common/ - Shared Utilities

## STRUCTURE
```
common/
├── __init__.py           # Re-exports: SQLOptConfig, RunPaths, errors, ProgressTracker
├── config.py             # SQLOptConfig + ConcurrencyConfig + load_config()
├── run_paths.py          # RunPaths - run directory management
├── progress.py           # ProgressTracker + StageProgress
├── errors.py             # SQLOptError hierarchy (5 types)
├── db_connector.py       # DBConnector + create_connector() for PG/MySQL
├── db_pool.py            # DBPoolBase + PostgresPool (connection pooling)
├── llm_mock_generator.py # LLMProviderBase + MockLLMProvider
├── mock_data_loader.py   # MockDataLoader - mock-first path resolution
├── concurrent.py         # ConcurrentExecutor + BatchOptions + TaskResult
├── contract_file_manager.py # Per-unit file I/O with atomic _index.json
└── summary_generator.py  # StageSummary + generate_summary_markdown()
```

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Add shared utility | Create here if used by 2+ stages |
| Config loading | `config.py` → `load_config()` |
| File paths | `run_paths.py` → `RunPaths` class |
| Error types | `errors.py` → `SQLOptError` hierarchy |
| DB operations | `db_connector.py` + `db_pool.py` |
| LLM integration | `llm_mock_generator.py` |
| Mock data | `mock_data_loader.py` |
| Parallel execution | `concurrent.py` |
| Per-unit files | `contract_file_manager.py` |
| SUMMARY.md generation | `summary_generator.py` |

## USAGE HEAT MAP
```
                    init  parse  recognition  optimize  result
config.py:           ✓      ✓        ✓           ✓        ✓
run_paths.py:        ✓      ✓        ✓           ✓        ✓
errors.py:           ✓      ✓        ✓           ✓        ✓
progress.py:         ✓      ✓        ✓           ✓        ✓
mock_data_loader.py: -      ✓        ✓           ✓        ✓
db_connector.py:     ✓      -        ✓           -        -
db_pool.py:          ✓      -        ✓           -        -
llm_mock_generator.py: -    -        ✓           ✓        -
concurrent.py:       -      -        ✓           ✓        -
contract_file_manager.py: - ✓        ✓           ✓        -
summary_generator.py: ✓     ✓        ✓           ✓        ✓
```

## CONVENTIONS
- All public symbols re-exported via `sqlopt.common` (see `__init__.py`)
- Error hierarchy: `SQLOptError` → `{ConfigError, StageError, ContractError, LLMError, DBError}`
- All errors have `to_dict()` for JSON serialization
- MockDataLoader intercepts file reads when `mock/` subdir exists
- ContractFileManager writes `units/{id}.json` + `units/_index.json` atomically
- Summary generation is pure (no file I/O) → caller handles writing
