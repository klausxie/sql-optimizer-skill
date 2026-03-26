# DECISION-001: Stage Structure

**Date**: 2026-03-24
**Status**: Accepted

## Context

The original V10 refactoring plan described a structure with `api.py` + `run.py` + domain modules per stage:

```
init/
├── api.py      # Input validation, output formatting
├── run.py      # Stage orchestration
├── scanner.py  # XML file scanning
├── parser.py   # XML parsing
└── table_extractor.py
```

## Decision

Implement a single `stage.py` file per stage that consolidates all logic:

```
init/
└── stage.py    # All logic in one file
```

## Rationale

- **Simpler imports**: `from sqlopt.stages.init import InitStage` instead of multiple module imports
- **Easier navigation**: All stage logic in one place
- **Reduced ceremony**: No need to maintain separate API and run concerns
- **CI-friendly**: Easier to test as a single unit

## Consequences

- Longer files (~400 lines) but better cohesion
- Each stage is self-contained
- No need for ContractValidator - stages validate internally
- Configuration passed via constructor or `run()` method

## Implementation

See `python/sqlopt/stages/{init,parse,recognition,optimize,result}/stage.py`
