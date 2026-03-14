"""Performance collector for SQL baseline execution.

Executes SQL statements in read-only transactions and collects performance metrics.
"""

from __future__ import annotations

import re
import time
from typing import Any


def _get_sql_connect():
    """Get SQL connection function and driver name."""
    try:
        import psycopg  # type: ignore

        return psycopg.connect, "psycopg"
    except Exception:
        pass

    try:
        import psycopg2  # type: ignore

        return psycopg2.connect, "psycopg2"
    except Exception:
        pass

    try:
        import pymysql

        return pymysql.connect, "pymysql"
    except Exception:
        pass

    try:
        import mysql.connector

        return mysql.connector.connect, "mysql-connector"
    except Exception:
        return None, None


def _parse_dsn(dsn: str) -> dict:
    import re

    if dsn.startswith("mysql://"):
        m = re.match(r"mysql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", dsn)
        if m:
            return {
                "user": m.group(1),
                "password": m.group(2),
                "host": m.group(3),
                "port": int(m.group(4)),
                "database": m.group(5),
            }
    return {}


def _substitute_bind_params(sql: str, params: dict[str, Any]) -> str:
    """Replace MyBatis #{} placeholders with actual values for execution.

    Args:
        sql: SQL with #{} placeholders
        params: Dictionary of parameter values

    Returns:
        SQL with #{} replaced by actual values
    """

    def replace_match(match):
        param_expr = match.group(1)
        param_name = re.split(r"[,\s]", param_expr)[0]
        if param_name in params:
            value = params[param_name]
            if value is None:
                return "NULL"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, str):
                escaped = value.replace("'", "''")
                return f"'{escaped}'"
            return str(value)
        return "NULL"

    return re.sub(r"#\{([^}]+)\}", replace_match, sql)


def _calculate_p95(values: list[float]) -> float:
    """Calculate the 95th percentile of a list of values.

    Args:
        values: List of numeric values

    Returns:
        The 95th percentile value
    """
    if not values:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate the index for the 95th percentile
    index = int(n * 0.95)

    # Clamp to valid range
    index = min(index, n - 1)

    return sorted_values[index]


def _execute_with_timeout(
    cursor: Any, sql: str, params: tuple | None, timeout_ms: int
) -> tuple[list, float]:
    """Execute SQL with timeout and return results with execution time.

    Args:
        cursor: Database cursor
        sql: SQL statement to execute
        params: Parameters for the SQL statement
        timeout_ms: Timeout in milliseconds

    Returns:
        Tuple of (rows, execution_time_ms)

    Raises:
        Exception: If execution fails or times out
    """
    start_time = time.time()

    # Set statement timeout
    cursor.execute(f"SET statement_timeout = {timeout_ms}")

    # Execute the query
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)

    # Fetch results
    rows = cursor.fetchall()

    end_time = time.time()
    execution_time_ms = (end_time - start_time) * 1000

    return rows, execution_time_ms


def _collect_explain_analyze(
    cursor: Any, sql: str, params: tuple | None, timeout_ms: int
) -> list[str]:
    """Collect EXPLAIN ANALYZE output for a SQL statement.

    Args:
        cursor: Database cursor
        sql: SQL statement to explain
        params: Parameters for the SQL statement
        timeout_ms: Timeout in milliseconds

    Returns:
        List of EXPLAIN ANALYZE output lines
    """
    try:
        # Set statement timeout
        cursor.execute(f"SET statement_timeout = {timeout_ms}")

        # Execute EXPLAIN ANALYZE
        explain_sql = f"EXPLAIN (ANALYZE TRUE, FORMAT TEXT) {sql}"
        if params:
            cursor.execute(explain_sql, params)
        else:
            cursor.execute(explain_sql)

        # Fetch explain results
        rows = cursor.fetchall()

        # Extract plan lines
        plan_lines = [str(row[0]) for row in rows]

        return plan_lines
    except Exception:
        # If EXPLAIN ANALYZE fails, return empty list
        return []


def collect_performance(
    config: dict[str, Any],
    sql: str,
    bound_params: dict[str, Any],
    runs: int = 5,
    timeout_ms: int = 3000,
) -> dict[str, Any]:
    """Execute SQL in read-only transaction and collect performance metrics.

    Args:
        config: Configuration dict with db.dsn for database connection
        sql: SQL statement to execute
        bound_params: Dictionary of bound parameters
        runs: Number of times to execute the SQL (default: 5)
        timeout_ms: Timeout in milliseconds (default: 3000)

    Returns:
        Dictionary with performance metrics:
        - avg_time_ms: Average execution time in milliseconds
        - min_time_ms: Minimum execution time in milliseconds
        - max_time_ms: Maximum execution time in milliseconds
        - p95_time_ms: 95th percentile execution time in milliseconds
        - total_runs: Total number of runs attempted
        - errors: Number of errors encountered
        - rows_returned: Number of rows returned (from first successful run)
        - explain_analyze_output: EXPLAIN ANALYZE output (if available)
        - error_details: List of error messages (if any)

    Raises:
        ValueError: If DSN is not set in config
        RuntimeError: If database driver is not available or connection fails
    """
    # Validate config
    dsn = (config.get("db", {}) or {}).get("dsn")
    if not dsn:
        raise ValueError("db.dsn not set in config")

    # Get database connection
    connect, driver = _get_sql_connect()
    if connect is None:
        raise RuntimeError(
            "No database driver available (psycopg, psycopg2, pymysql, or mysql-connector)"
        )

    # Initialize metrics
    execution_times: list[float] = []
    errors = 0
    error_details: list[str] = []
    rows_returned = 0
    explain_analyze_output: list[str] = []

    # Prepare SQL by replacing MyBatis #{} placeholders with actual values
    executable_sql = _substitute_bind_params(sql, bound_params or {})

    is_mysql = driver in ("pymysql", "mysql-connector")
    conn = None

    try:
        if is_mysql:
            db_config = _parse_dsn(dsn)
            conn = connect(
                host=db_config.get("host"),
                port=db_config.get("port", 3306),
                user=db_config.get("user"),
                password=db_config.get("password"),
                database=db_config.get("database"),
            )
        else:
            conn = connect(dsn)
            for run in range(runs):
                cur = None
                try:
                    cur = conn.cursor()
                    cur.execute("BEGIN READ ONLY")

                    rows, exec_time = _execute_with_timeout(
                        cur, executable_sql, None, timeout_ms
                    )

                    execution_times.append(exec_time)

                    if run == 0:
                        rows_returned = len(rows)

                except Exception as e:
                    errors += 1
                    error_msg = str(e)
                    if error_msg not in error_details:
                        error_details.append(error_msg)
                finally:
                    if cur is not None:
                        try:
                            cur.execute("ROLLBACK")
                        except Exception:
                            pass
                        finally:
                            try:
                                cur.close()
                            except Exception:
                                pass

            if execution_times:
                cur = None
                try:
                    cur = conn.cursor()
                    cur.execute("BEGIN READ ONLY")
                    explain_analyze_output = _collect_explain_analyze(
                        cur, executable_sql, None, timeout_ms
                    )
                except Exception:
                    pass
                finally:
                    if cur is not None:
                        try:
                            cur.execute("ROLLBACK")
                        except Exception:
                            pass
                        finally:
                            try:
                                cur.close()
                            except Exception:
                                pass

    except Exception as e:
        # Connection-level error
        raise RuntimeError(f"Failed to connect to database: {e}")
    finally:
        if is_mysql and conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # Calculate statistics
    if execution_times:
        avg_time = sum(execution_times) / len(execution_times)
        min_time = min(execution_times)
        max_time = max(execution_times)
        p95_time = _calculate_p95(execution_times)
    else:
        # All runs failed
        avg_time = 0.0
        min_time = 0.0
        max_time = 0.0
        p95_time = 0.0

    # Build result
    result = {
        "avg_time_ms": round(avg_time, 2),
        "min_time_ms": round(min_time, 2),
        "max_time_ms": round(max_time, 2),
        "p95_time_ms": round(p95_time, 2),
        "total_runs": runs,
        "errors": errors,
        "rows_returned": rows_returned,
        "explain_analyze_output": explain_analyze_output,
    }

    # Include error details if any
    if error_details:
        result["error_details"] = error_details
        result["last_error"] = error_details[-1] if error_details else None

    return result
