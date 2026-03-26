# DECISION-002: Patch Mechanism

**Date**: 2026-03-24
**Status**: Accepted

## Context

The original V10 plan described a structured patch mechanism with action types:

```
REPLACE  # Replace SQL text
ADD      # Add new SQL
REMOVE   # Remove SQL
WRAP     # Wrap existing SQL with new logic
```

Each action would include XPath tracking and semantic verification.

## Decision

Use Python's `difflib.unified_diff()` to generate plain unified diff text for SQL patches.

## Rationale

- **Simple**: No need for structured action system
- **Sufficient**: SQL diffs are straightforward text differences
- **No complexity**: Avoid XPath tracking and semantic verification overhead
- **Standard format**: Git/monotone compatible

## Consequences

- No structured action types - just plain diff text
- `_create_patch()` in `result/stage.py` generates unified diff
- No `patch_generator.py`, `xml_applier.py`, or `diff_generator.py`

## Unimplemented Design

See `../archive/v10-refactor-original/STAGES/patch.md` for the full structured patch design that was not implemented.

## Implementation

See `python/sqlopt/stages/result/stage.py` - `_create_patch()` method.
