# DECISION-005: Per-Unit File Format

**Date**: 2026-03-25
**Status**: Accepted

## Context

Parse, Recognition, and Optimize stages process SQL units individually. The original design wrote aggregated JSON files per stage.

## Decision

Write per-unit JSON files alongside aggregated output:

```
runs/{run_id}/parse/
├── sql_units_with_branches.json    # Aggregated index
└── units/
    ├── {unit_id}.json            # Per-unit data
    └── _index.json               # Index of all units
```

## Rationale

- **Granular access**: Load single unit data without parsing large files
- **Parallel processing**: Units can be processed independently
- **Easier debugging**: Find specific unit data without searching large files
- **ContractFileManager**: Centralized per-unit file I/O

## Consequences

- More files on disk but smaller individual files
- Aggregated files remain for backward compatibility
- Recognition and Optimize can process units in parallel

## Implementation

See `python/sqlopt/common/contract_file_manager.py` - `ContractFileManager` class.
