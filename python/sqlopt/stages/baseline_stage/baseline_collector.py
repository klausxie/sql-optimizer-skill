"""
V8 Baseline Stage - Performance Data Collection

Collects SQL execution performance metrics through EXPLAIN and actual execution.
Zero coupling with legacy code.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json
import re
import time


@dataclass
class BaselineResult:
    sql_key: str
    execution_time_ms: float
    rows_examined: int
    rows_returned: int
    explain_plan: dict
    database_platform: str
    sample_params: dict


@dataclass
class ExplainPlan:
    plan_text: str
    estimated_cost: Optional[float]
    estimated_rows: Optional[int]
    scan_type: str


def _parse_dsn(dsn: str) -> dict:
    if dsn.startswith("mysql://"):
        m = re.match(r"mysql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", dsn)
        if m:
            return {
                "platform": "mysql",
                "user": m.group(1),
                "password": m.group(2),
                "host": m.group(3),
                "port": int(m.group(4)),
                "database": m.group(5),
            }
    elif dsn.startswith("postgresql://"):
        m = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", dsn)
        if m:
            return {
                "platform": "postgresql",
                "user": m.group(1),
                "password": m.group(2),
                "host": m.group(3),
                "port": int(m.group(4)),
                "database": m.group(5),
            }
    return {}


def _substitute_bind_params(sql: str, params: dict[str, Any]) -> str:
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
            return f"'{value}'"
        return match.group(0)

    return re.sub(r"#\{([^}]+)\}", replace_match, sql)


def _extract_param_names(sql: str) -> list[str]:
    return re.findall(r"#\{([^},]+)", sql)


def _get_connection(dsn: str):
    db_info = _parse_dsn(dsn)
    platform = db_info.get("platform", "")

    if platform == "postgresql":
        try:
            import psycopg

            return psycopg.connect(dsn), platform
        except Exception:
            pass
        try:
            import psycopg2

            return psycopg2.connect(dsn), platform
        except Exception:
            pass
    elif platform == "mysql":
        try:
            import pymysql

            return pymysql.connect(dsn), platform
        except Exception:
            pass
        try:
            import mysql.connector

            return mysql.connector.connect(dsn), platform
        except Exception:
            pass

    return None, None


def _run_explain(conn, platform: str, sql: str, params: dict) -> ExplainPlan:
    bound_sql = _substitute_bind_params(sql, params)

    if platform == "mysql":
        explain_sql = f"EXPLAIN {bound_sql}"
    else:
        explain_sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS) {bound_sql}"

    with conn.cursor() as cursor:
        cursor.execute(explain_sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        plan_data = {}
        if rows:
            for col, val in zip(columns, rows[0]):
                plan_data[col] = val

        plan_text = json.dumps(plan_data, ensure_ascii=False)

        scan_type = "UNKNOWN"
        estimated_cost = None
        estimated_rows = None

        if platform == "mysql":
            scan_type = plan_data.get("type", "UNKNOWN")
            estimated_rows = plan_data.get("rows")
        else:
            scan_type = plan_data.get("Plan", {}).get("Node Type", "UNKNOWN")
            estimated_cost = plan_data.get("Plan", {}).get("Total Cost")
            estimated_rows = plan_data.get("Plan", {}).get("Plan Rows")

        return ExplainPlan(
            plan_text=plan_text,
            estimated_cost=estimated_cost,
            estimated_rows=estimated_rows,
            scan_type=scan_type,
        )


def _execute_and_measure(
    conn, sql: str, params: dict, platform: str
) -> tuple[int, float]:
    bound_sql = _substitute_bind_params(sql, params)

    start_time = time.perf_counter()
    with conn.cursor() as cursor:
        cursor.execute(bound_sql)
        rows = cursor.fetchall()
        row_count = len(rows)
    end_time = time.perf_counter()

    return row_count, (end_time - start_time) * 1000


class BaselineCollector:
    def __init__(self, config: dict):
        self.config = config
        self.db_dsn = config.get("db", {}).get("dsn", "")

    def collect(self, sql_unit: dict) -> BaselineResult:
        sql = sql_unit.get("sql", "")
        sql_key = sql_unit.get("sqlKey", "unknown")
        params = sql_unit.get("paramExample", {})

        conn, platform = _get_connection(self.db_dsn)
        if conn is None:
            return BaselineResult(
                sql_key=sql_key,
                execution_time_ms=0,
                rows_examined=0,
                rows_returned=0,
                explain_plan={},
                database_platform="unknown",
                sample_params=params,
            )

        try:
            db_platform = platform or "postgresql"
            explain_plan = _run_explain(conn, db_platform, sql, params)
            rows_returned, exec_time = _execute_and_measure(
                conn, sql, params, db_platform
            )

            return BaselineResult(
                sql_key=sql_key,
                execution_time_ms=exec_time,
                rows_examined=explain_plan.estimated_rows or rows_returned,
                rows_returned=rows_returned,
                explain_plan={
                    "plan_text": explain_plan.plan_text,
                    "scan_type": explain_plan.scan_type,
                    "estimated_cost": explain_plan.estimated_cost,
                    "estimated_rows": explain_plan.estimated_rows,
                },
                database_platform=db_platform,
                sample_params=params,
            )
        finally:
            conn.close()

    def collect_batch(self, sql_units: list[dict]) -> list[BaselineResult]:
        results = []
        for unit in sql_units:
            result = self.collect(unit)
            results.append(result)
        return results


def collect_baseline(config: dict, sql_units: list[dict]) -> list[dict]:
    collector = BaselineCollector(config)
    results = collector.collect_batch(sql_units)
    return [
        {
            "sqlKey": r.sql_key,
            "executionTimeMs": r.execution_time_ms,
            "rowsExamined": r.rows_examined,
            "rowsReturned": r.rows_returned,
            "explainPlan": r.explain_plan,
            "databasePlatform": r.database_platform,
            "sampleParams": r.sample_params,
        }
        for r in results
    ]
