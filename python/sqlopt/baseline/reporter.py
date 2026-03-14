"""Baseline performance report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def generate_baseline_report(
    performance_metrics: dict[str, Any],
    sql_unit: dict[str, Any],
) -> dict[str, Any]:
    """Generate a structured baseline performance report.

    Args:
        performance_metrics: Performance metrics from collect_performance
            - avg_time_ms: Average execution time in milliseconds
            - min_time_ms: Minimum execution time in milliseconds
            - max_time_ms: Maximum execution time in milliseconds
            - p95_time_ms: 95th percentile execution time in milliseconds
            - total_runs: Total number of runs attempted
            - errors: Number of errors encountered
            - rows_returned: Number of rows returned
            - explain_analyze_output: EXPLAIN ANALYZE output lines

        sql_unit: SQL unit information
            - sqlKey: Unique key for the SQL statement
            - parameters: List of parameter dicts with name/value

    Returns:
        Structured report dictionary with fields:
        - sqlKey: SQL statement identifier
        - timestamp: ISO 8601 timestamp
        - executionStats: Execution statistics
        - rowsReturned: Number of rows returned
        - explainPlan: EXPLAIN plan output
        - parameters: Parameter values used
        - dataSampled: Whether data was sampled (always True for baseline)
    """
    # Extract execution stats with renamed keys
    execution_stats = {
        "avgTimeMs": performance_metrics.get("avg_time_ms", 0.0),
        "minTimeMs": performance_metrics.get("min_time_ms", 0.0),
        "maxTimeMs": performance_metrics.get("max_time_ms", 0.0),
        "p95Ms": performance_metrics.get("p95_time_ms", 0.0),
        "totalRuns": performance_metrics.get("total_runs", 0),
        "errors": performance_metrics.get("errors", 0),
    }

    # Get parameters from sql_unit, default to empty list
    parameters = sql_unit.get("parameters", [])

    # Get explain plan output
    explain_plan = performance_metrics.get("explain_analyze_output", [])

    # Get rows returned
    rows_returned = performance_metrics.get("rows_returned", 0)

    # Build the report
    report = {
        "sqlKey": sql_unit.get("sqlKey", "unknown"),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executionStats": execution_stats,
        "rowsReturned": rows_returned,
        "explainPlan": explain_plan,
        "parameters": parameters,
        "dataSampled": True,
    }

    return report


def write_report_jsonl(report: dict[str, Any], output_path: str) -> None:
    """Write a baseline report to a JSONL file.

    Args:
        report: The report dictionary to write
        output_path: Path to the output JSONL file

    Raises:
        IOError: If file cannot be written
    """
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")
