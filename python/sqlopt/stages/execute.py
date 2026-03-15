"""Execute SQL and collect performance data.

This stage handles:
- Execute SQL with EXPLAIN
- Collect execution plans
- Measure actual execution time
- Collect row counts
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExecuteResult:
    """SQL execution result."""
    branch_id: str
    sql: str
    plan: str           # EXPLAIN output
    duration_ms: int    # Execution time in milliseconds
    rows: int           # Number of rows returned
    error: str | None = None


def execute_sql_branch(
    branch_sql: str,
    db_dsn: str,
    branch_id: str = "default"
) -> ExecuteResult:
    """Execute a single SQL branch with EXPLAIN.
    
    Args:
        branch_sql: The SQL to execute
        db_dsn: Database connection string
        branch_id: Identifier for this branch
        
    Returns:
        ExecuteResult with plan, duration, and row count
    """
    # Import database driver based on platform
    if db_dsn.startswith("mysql"):
        return _execute_mysql(branch_sql, db_dsn, branch_id)
    elif db_dsn.startswith("postgresql"):
        return _execute_postgresql(branch_sql, db_dsn, branch_id)
    else:
        return ExecuteResult(
            branch_id=branch_id,
            sql=branch_sql,
            plan="",
            duration_ms=0,
            rows=0,
            error=f"Unsupported database platform: {db_dsn}"
        )


def _execute_mysql(sql: str, dsn: str, branch_id: str) -> ExecuteResult:
    """Execute SQL on MySQL."""
    try:
        import pymysql
        
        # Parse DSN
        # mysql://user:password@host:port/database
        parts = dsn.replace("mysql://", "").split("@")
        user_pass = parts[0].split(":")
        host_db = parts[1].split("/")
        host_port = host_db[0].split(":")
        
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1] if len(host_db) > 1 else ""
        
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        cursor = conn.cursor()
        
        # Get EXPLAIN
        start_time = time.time()
        cursor.execute(f"EXPLAIN {sql}")
        explain_result = cursor.fetchall()
        explain_str = str(explain_result)
        
        # Execute actual query to get row count
        cursor.execute(sql)
        rows = cursor.fetchone()[0] if cursor.description else 0
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        cursor.close()
        conn.close()
        
        return ExecuteResult(
            branch_id=branch_id,
            sql=sql,
            plan=explain_str,
            duration_ms=duration_ms,
            rows=rows
        )
        
    except Exception as e:
        return ExecuteResult(
            branch_id=branch_id,
            sql=sql,
            plan="",
            duration_ms=0,
            rows=0,
            error=str(e)
        )


def _execute_postgresql(sql: str, dsn: str, branch_id: str) -> ExecuteResult:
    """Execute SQL on PostgreSQL."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor()
        
        # Get EXPLAIN
        start_time = time.time()
        cursor.execute(f"EXPLAIN {sql}")
        explain_result = cursor.fetchall()
        explain_str = "\n".join([str(row) for row in explain_result])
        
        # Execute with LIMIT to avoid huge result sets
        cursor.execute(f"{sql} LIMIT 1")
        rows = cursor.rowcount
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        cursor.close()
        conn.close()
        
        return ExecuteResult(
            branch_id=branch_id,
            sql=sql,
            plan=explain_str,
            duration_ms=duration_ms,
            rows=rows
        )
        
    except Exception as e:
        return ExecuteResult(
            branch_id=branch_id,
            sql=sql,
            plan="",
            duration_ms=0,
            rows=0,
            error=str(e)
        )


def mock_execute(branch_sql: str, branch_id: str = "default") -> ExecuteResult:
    """Mock execution for when no database is available.
    
    Returns a placeholder result indicating this is a mock.
    """
    return ExecuteResult(
        branch_id=branch_id,
        sql=branch_sql,
        plan="MOCK: No database connection - use LLM to estimate",
        duration_ms=0,
        rows=0,
        error=None
    )
