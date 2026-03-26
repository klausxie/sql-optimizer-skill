# Common Modules

## Overview

Shared utilities used across all stages.

## Modules

| Module | Purpose |
|--------|---------|
| `config.py` | SQLOptConfig dataclass, YAML loading |
| `run_paths.py` | Run directory management |
| `progress.py` | ProgressTracker for stage monitoring |
| `progress_display.py` | User-friendly progress bar (TTY/non-TTY) |
| `errors.py` | SQLOptError hierarchy (5 types) |
| `db_connector.py` | PostgreSQL/MySQL connectors |
| `db_pool.py` | Connection pooling |
| `llm_mock_generator.py` | MockLLMProvider for baselines/suggestions |
| `mock_data_loader.py` | Mock-first path resolution |
| `concurrent.py` | ConcurrentExecutor for parallel work |
| `contract_file_manager.py` | Per-unit JSON file I/O |
| `summary_generator.py` | SUMMARY.md generation |

## Usage Heat Map

| Module | init | parse | recognition | optimize | result |
|--------|------|-------|-------------|----------|--------|
| config | ✓ | ✓ | ✓ | ✓ | ✓ |
| run_paths | ✓ | ✓ | ✓ | ✓ | ✓ |
| progress | ✓ | ✓ | ✓ | ✓ | ✓ |
| progress_display | ✓ | ✓ | ✓ | ✓ | ✓ |
| errors | ✓ | ✓ | ✓ | ✓ | ✓ |
| db_connector | ✓ | - | ✓ | - | - |
| llm_mock | - | - | ✓ | ✓ | - |
| concurrent | - | - | ✓ | ✓ | - |
| contract_file | - | ✓ | ✓ | ✓ | - |
| summary | ✓ | - | - | - | ✓ |

## Note on progress.py vs progress_display.py

- `progress.py`: Internal progress tracking (ProgressTracker class)
- `progress_display.py`: User-visible progress output (ProgressDisplay class)
