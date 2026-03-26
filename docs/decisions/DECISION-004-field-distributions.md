# DECISION-004: WHERE Field Distribution Collection

**Date**: 2026-03-25
**Status**: Accepted

## Context

The Optimize stage needs selectivity information for WHERE clause fields to assess query performance risk.

## Decision

Collect column statistics (value distribution, cardinality) in the Init stage via `extract_field_distributions()`.

## Implementation

```python
# table_extractor.py
def extract_field_distributions(
    table_name: str,
    column_names: List[str],
    db_connector: DBConnector,
    platform: str,
    top_n: int = 10,
) -> List[FieldDistribution]
```

## Output

Written to `runs/{run_id}/init/field_distributions.json`:

```json
{
  "table_name": "orders",
  "column_name": "status",
  "distinct_count": 5,
  "null_count": 0,
  "top_values": [
    {"value": "pending", "count": 150},
    {"value": "completed", "count": 120}
  ],
  "min_value": "cancelled",
  "max_value": "pending"
}
```

## Usage

Recognition stage uses field distributions for risk scoring:
- High cardinality fields: higher selectivity risk
- Low cardinality fields: may indicate unbalanced data

## Consequences

- Init stage takes longer (DB queries per WHERE field)
- Risk scoring in Recognition more accurate
- Progress tracking added for distribution extraction

## Implementation

See `python/sqlopt/stages/init/table_extractor.py` and `python/sqlopt/stages/init/stage.py`
