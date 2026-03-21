"""
Performance data collector for baseline measurements.

Shim module for legacy import compatibility.
"""

import re
from typing import Any, Optional


def _get_sql_connect():
    """Get SQL connection driver. Returns (driver, name) tuple."""
    # Stub - returns a mock driver for testing
    return ("mock_driver", "mock_connection")


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse database DSN string."""
    match = re.match(
        r"mysql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/(?P<database>\w+)",
        dsn,
    )
    if match:
        result = match.groupdict()
        result["port"] = int(result["port"])
        return result
    return {}


def _substitute_bind_params(sql: str, params: dict[str, Any]) -> str:
    """Substitute #{param} placeholders with actual values."""
    result = sql
    for key, value in params.items():
        placeholder = f"#{{{key}}}"
        if value is None:
            result = result.replace(placeholder, "NULL")
        elif isinstance(value, bool):
            result = result.replace(placeholder, "true" if value else "false")
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            result = result.replace(placeholder, f"'{escaped}'")
        elif isinstance(value, (int, float)):
            result = result.replace(placeholder, str(value))
        else:
            result = result.replace(placeholder, str(value))
    result = re.sub(r"#\{[^}]+\}", "NULL", result)
    return result


def _calculate_p95(values: list[float]) -> float:
    """Calculate 95th percentile of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    index = int(len(sorted_vals) * 0.95)
    if index >= len(sorted_vals):
        index = len(sorted_vals) - 1
    return sorted_vals[index]


def collect_performance(config: dict, sql: str, params: dict[str, Any]) -> dict:
    """Collect performance metrics for a SQL query."""
    if "db" not in config or "dsn" not in config.get("db", {}):
        raise ValueError("db.dsn not set")
    # Stub implementation
    return {
        "execution_time_ms": 0.0,
        "rows_examined": 0,
        "rows_returned": 0,
    }
