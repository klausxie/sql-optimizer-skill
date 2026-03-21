"""
Baseline Stage Module (V8)

Performance baseline collection and testing.

Supports:
- PostgreSQL EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)
- MySQL EXPLAIN FORMAT=JSON and EXPLAIN ANALYZE (8.0.18+)
"""

from .baseline_collector import (
    BaselineCollector,
    BaselineResult,
    ExplainPlan,
    ExplainParseResult,
    collect_baseline,
    _parse_postgresql_explain_json,
    _parse_mysql_explain_json,
)

__all__ = [
    "BaselineCollector",
    "BaselineResult",
    "ExplainPlan",
    "ExplainParseResult",
    "collect_baseline",
    "_parse_postgresql_explain_json",
    "_parse_mysql_explain_json",
]
