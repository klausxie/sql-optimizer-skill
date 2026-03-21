"""
V8 Baseline Stage - Performance Data Collection

Collects SQL execution performance metrics through EXPLAIN and actual execution.
Zero coupling with legacy code.

Supports:
- PostgreSQL: EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)
- MySQL: EXPLAIN FORMAT=JSON, EXPLAIN ANALYZE (8.0.18+)
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
    # Extended metrics
    actual_execution_time_ms: Optional[float] = None
    buffer_hit_count: Optional[int] = None
    buffer_read_count: Optional[int] = None
    index_used: Optional[str] = None


@dataclass
class ExplainPlan:
    plan_text: str
    estimated_cost: Optional[float] = None
    estimated_rows: Optional[int] = None
    scan_type: str = "UNKNOWN"
    # Extended fields from JSON explain
    actual_rows: Optional[int] = None
    actual_loops: Optional[int] = None
    actual_startup_time_ms: Optional[float] = None
    actual_total_time_ms: Optional[float] = None
    index_name: Optional[str] = None
    filter_condition: Optional[str] = None
    # PostgreSQL specific
    shared_read_blocks: Optional[int] = None
    shared_hit_blocks: Optional[int] = None
    shared_dirtied_blocks: Optional[int] = None
    shared_written_blocks: Optional[int] = None
    # MySQL specific
    query_cost: Optional[float] = None
    data_read_per_join: Optional[str] = None
    used_columns: Optional[list] = None
    attachable_conditions: Optional[list] = None


@dataclass
class ExplainParseResult:
    """Result of parsing EXPLAIN output."""

    plan: ExplainPlan
    raw_json: Optional[dict] = None
    warnings: list[str] = field(default_factory=list)


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


# =============================================================================
# PostgreSQL EXPLAIN JSON Parser
# =============================================================================


def _parse_postgresql_explain_json(explain_result: list) -> ExplainParseResult:
    """
    Parse PostgreSQL EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) output.

    PostgreSQL JSON explain structure:
    [
      {
        "Plan": {
          "Node Type": "Seq Scan",
          "Relation Name": "users",
          "Alias": "users",
          "Startup Cost": 0.00,
          "Total Cost": 1234.56,
          "Plan Rows": 10000,
          "Plan Width": 100,
          "Actual Startup Time": 0.012,
          "Actual Total Time": 5.678,
          "Actual Rows": 9500,
          "Actual Loops": 1,
          "Shared Read Blocks": 100,
          "Shared Hit Blocks": 50,
          "Shared Dirtied Blocks": 0,
          "Shared Written Blocks": 0,
          ...
        },
        "Planning Time": 0.123,
        "Triggers": [],
        "Execution Time": 5.789
      }
    ]
    """
    warnings = []

    if not explain_result or not isinstance(explain_result, list):
        return ExplainParseResult(
            plan=ExplainPlan(
                plan_text="{}",
                estimated_cost=None,
                estimated_rows=None,
                scan_type="UNKNOWN",
            ),
            raw_json=None,
            warnings=["Empty or invalid EXPLAIN result"],
        )

    plan_data = explain_result[0] if explain_result else {}
    root_plan = plan_data.get("Plan", {})

    # Extract basic fields
    node_type = root_plan.get("Node Type", "UNKNOWN")
    relation_name = root_plan.get("Relation Name", "")

    # Determine scan type from node type
    scan_type_map = {
        "Seq Scan": "FULL_TABLE_SCAN",
        "Index Scan": "INDEX_SCAN",
        "Index Only Scan": "INDEX_ONLY_SCAN",
        "Bitmap Index Scan": "BITMAP_INDEX_SCAN",
        "Bitmap Heap Scan": "BITMAP_HEAP_SCAN",
        "Nested Loop": "NESTED_LOOP",
        "Hash Join": "HASH_JOIN",
        "Merge Join": "MERGE_JOIN",
        "Sort": "SORT",
        "Aggregate": "AGGREGATE",
        "HashAggregate": "HASH_AGGREGATE",
        "GroupAggregate": "GROUP_AGGREGATE",
        "Limit": "LIMIT",
        "Gather": "GATHER",
        "Gather Merge": "GATHER_MERGE",
    }
    scan_type = scan_type_map.get(node_type, node_type) or "UNKNOWN"

    # Extract index name if present
    index_name = root_plan.get("Index Name")
    if not index_name and "Index Cond" in root_plan:
        # Try to extract index name from Index Cond
        index_cond = root_plan.get("Index Cond", "")
        idx_match = re.search(r"(\w+)_idx", index_cond)
        if idx_match:
            index_name = idx_match.group(1)

    # Build ExplainPlan
    plan = ExplainPlan(
        plan_text=json.dumps(explain_result, ensure_ascii=False),
        estimated_cost=root_plan.get("Total Cost"),
        estimated_rows=root_plan.get("Plan Rows"),
        scan_type=scan_type,
        actual_rows=root_plan.get("Actual Rows"),
        actual_loops=root_plan.get("Actual Loops"),
        actual_startup_time_ms=root_plan.get("Actual Startup Time"),
        actual_total_time_ms=root_plan.get("Actual Total Time"),
        index_name=index_name,
        filter_condition=root_plan.get("Filter"),
        shared_read_blocks=root_plan.get("Shared Read Blocks"),
        shared_hit_blocks=root_plan.get("Shared Hit Blocks"),
        shared_dirtied_blocks=root_plan.get("Shared Dirtied Blocks"),
        shared_written_blocks=root_plan.get("Shared Written Blocks"),
    )

    # Add warnings for potential issues
    if root_plan.get("Actual Rows", 0) > root_plan.get("Plan Rows", 0) * 10:
        warnings.append(
            f"Actual rows ({root_plan.get('Actual Rows')}) much larger than estimated ({root_plan.get('Plan Rows')})"
        )

    return ExplainParseResult(
        plan=plan,
        raw_json=plan_data,
        warnings=warnings,
    )


# =============================================================================
# MySQL EXPLAIN JSON Parser
# =============================================================================


def _parse_mysql_explain_json(explain_result: dict) -> ExplainParseResult:
    """
    Parse MySQL EXPLAIN FORMAT=JSON output.

    MySQL JSON explain structure:
    {
      "query_block": {
        "select_id": 1,
        "cost_info": {
          "query_cost": "1234.56"
        },
        "table": {
          "table_name": "users",
          "access_type": "ref",
          "possible_keys": ["idx_name"],
          "key": "idx_name",
          "used_key_parts": ["name"],
          "key_length": "102",
          "ref": ["const"],
          "rows_examined_per_scan": 100,
          "rows_produced_per_join": 100,
          "filtered": "100.00",
          "cost_info": {
            "read_cost": "10.00",
            "eval_cost": "1.00",
            ...
          },
          "used_columns": ["id", "name", "email"],
          "attached_condition": "(`db`.`users`.`status` = 'active')"
        },
        ...
      }
    }

    For MySQL 8.0.18+ EXPLAIN ANALYZE:
    {
      "query_block": {
        "select_id": 1,
        "cost_info": {...},
        "table": {
          ...
          "analyze": {
            "rows_examined_per_scan": 100,
            "r_rows": 95.0,  // actual rows
            "r_total_time_ms": 5.67  // actual time
          }
        }
      }
    }
    """
    warnings = []

    if not explain_result or not isinstance(explain_result, dict):
        return ExplainParseResult(
            plan=ExplainPlan(
                plan_text="{}",
                estimated_cost=None,
                estimated_rows=None,
                scan_type="UNKNOWN",
            ),
            raw_json=None,
            warnings=["Empty or invalid EXPLAIN result"],
        )

    query_block = explain_result.get("query_block", {})

    # Extract query cost
    cost_info = query_block.get("cost_info", {})
    query_cost = None
    if "query_cost" in cost_info:
        try:
            query_cost = float(cost_info["query_cost"])
        except (ValueError, TypeError):
            pass

    # Find first table node (recursively)
    def find_table_node(node: dict) -> dict:
        if "table" in node:
            return node["table"]
        for key, value in node.items():
            if isinstance(value, dict):
                result = find_table_node(value)
                if result:
                    return result
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        result = find_table_node(item)
                        if result:
                            return result
        return {}

    table_node = find_table_node(query_block)

    # Map MySQL access_type to our scan types
    access_type_map = {
        "system": "SYSTEM",
        "const": "CONST",
        "eq_ref": "EQ_REF",
        "ref": "INDEX_REF",
        "fulltext": "FULLTEXT",
        "ref_or_null": "REF_OR_NULL",
        "index_merge": "INDEX_MERGE",
        "unique_subquery": "UNIQUE_SUBQUERY",
        "index_subquery": "INDEX_SUBQUERY",
        "range": "INDEX_RANGE_SCAN",
        "index": "FULL_INDEX_SCAN",
        "ALL": "FULL_TABLE_SCAN",
    }
    access_type = table_node.get("access_type") or "UNKNOWN"
    scan_type = access_type_map.get(
        access_type, access_type.upper() if access_type else "UNKNOWN"
    )

    # Extract rows examined
    rows_examined = table_node.get("rows_examined_per_scan")
    if rows_examined is None:
        rows_examined = table_node.get("rows_produced_per_join")

    # Extract actual metrics from EXPLAIN ANALYZE (MySQL 8.0.18+)
    analyze_node = table_node.get("analyze", {})
    actual_rows = None
    actual_time_ms = None
    if analyze_node:
        r_rows = analyze_node.get("r_rows")
        if r_rows is not None:
            try:
                actual_rows = int(float(r_rows))
            except (ValueError, TypeError):
                pass
        r_total_time = analyze_node.get("r_total_time_ms")
        if r_total_time is not None:
            try:
                actual_time_ms = float(r_total_time)
            except (ValueError, TypeError):
                pass

    # Extract index info
    index_name = table_node.get("key")
    possible_keys = table_node.get("possible_keys", [])
    if not index_name and possible_keys:
        # No index used but possible keys exist
        warnings.append(f"Possible keys not used: {possible_keys}")

    # Extract used columns
    used_columns = table_node.get("used_columns", [])

    # Extract attached conditions
    attached_condition = table_node.get("attached_condition", "")
    attachable_conditions = [attached_condition] if attached_condition else []

    # Build ExplainPlan
    plan = ExplainPlan(
        plan_text=json.dumps(explain_result, ensure_ascii=False),
        estimated_cost=query_cost,
        estimated_rows=rows_examined,
        scan_type=scan_type,
        actual_rows=actual_rows,
        actual_total_time_ms=actual_time_ms,
        index_name=index_name,
        filter_condition=attached_condition,
        query_cost=query_cost,
        used_columns=used_columns,
        attachable_conditions=attachable_conditions,
    )

    # Add warnings for table scans
    if scan_type == "FULL_TABLE_SCAN":
        warnings.append("Full table scan detected")

    return ExplainParseResult(
        plan=plan,
        raw_json=explain_result,
        warnings=warnings,
    )


def _get_connection(dsn: str):
    db_info = _parse_dsn(dsn)
    platform = db_info.get("platform", "")

    if platform == "postgresql":
        try:
            import psycopg  # type: ignore

            return psycopg.connect(dsn), platform
        except Exception:
            pass
        try:
            import psycopg2  # type: ignore

            return psycopg2.connect(dsn), platform
        except Exception:
            pass
    elif platform == "mysql":
        try:
            import pymysql  # type: ignore

            # pymysql requires keyword arguments, not DSN string
            return pymysql.connect(
                host=db_info["host"],
                port=db_info["port"],
                user=db_info["user"],
                password=db_info["password"],
                database=db_info["database"],
                charset="utf8mb4",
            ), platform
        except Exception:
            pass
        try:
            import mysql.connector  # type: ignore

            return mysql.connector.connect(
                host=db_info["host"],
                port=db_info["port"],
                user=db_info["user"],
                password=db_info["password"],
                database=db_info["database"],
            ), platform
        except Exception:
            pass

    return None, None


def _run_explain(conn, platform: str, sql: str, params: dict) -> ExplainParseResult:
    """
    Execute EXPLAIN and parse result based on platform.

    For PostgreSQL: EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)
    For MySQL: EXPLAIN FORMAT=JSON

    Returns ExplainParseResult with parsed plan and warnings.
    """
    bound_sql = _substitute_bind_params(sql, params)

    if platform == "mysql":
        # MySQL: Use JSON format for detailed explain
        explain_sql = f"EXPLAIN FORMAT=JSON {bound_sql}"

        with conn.cursor() as cursor:
            try:
                cursor.execute(explain_sql)
                row = cursor.fetchone()

                if row and len(row) > 0:
                    explain_result = row[0]
                    if isinstance(explain_result, str):
                        try:
                            explain_result = json.loads(explain_result)
                        except json.JSONDecodeError:
                            return ExplainParseResult(
                                plan=ExplainPlan(
                                    plan_text=explain_result,
                                    estimated_cost=None,
                                    estimated_rows=None,
                                    scan_type="PARSE_ERROR",
                                ),
                                warnings=["Failed to parse JSON explain"],
                            )

                    return _parse_mysql_explain_json(explain_result)
            except Exception as e:
                # Fallback to traditional EXPLAIN
                return _run_explain_mysql_traditional(conn, bound_sql)
    else:
        # PostgreSQL: Use JSON format with ANALYZE for actual metrics
        explain_sql = (
            f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {bound_sql}"
        )

        with conn.cursor() as cursor:
            try:
                cursor.execute(explain_sql)
                rows = cursor.fetchall()

                # PostgreSQL returns list of tuples, first element is the JSON
                explain_result = []
                for row in rows:
                    if row and len(row) > 0:
                        json_str = row[0]
                        if isinstance(json_str, str):
                            try:
                                explain_result.append(json.loads(json_str))
                            except json.JSONDecodeError:
                                # Try to parse as combined JSON (psycopg2 returns in chunks)
                                pass
                        elif isinstance(json_str, dict):
                            explain_result.append(json_str)

                if explain_result:
                    return _parse_postgresql_explain_json(explain_result)

            except Exception as e:
                # Fallback to traditional EXPLAIN without ANALYZE
                return _run_explain_postgresql_traditional(conn, bound_sql)

    return ExplainParseResult(
        plan=ExplainPlan(
            plan_text="{}",
            estimated_cost=None,
            estimated_rows=None,
            scan_type="UNKNOWN",
        ),
        warnings=["No explain result obtained"],
    )


def _run_explain_mysql_traditional(conn, bound_sql: str) -> ExplainParseResult:
    """Fallback MySQL EXPLAIN parser for traditional format."""
    explain_sql = f"EXPLAIN {bound_sql}"

    with conn.cursor() as cursor:
        cursor.execute(explain_sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        plan_data = {}
        if rows:
            for col, val in zip(columns, rows[0]):
                plan_data[col] = val

        # Map MySQL type to scan type
        access_type = plan_data.get("type") or "ALL"
        access_type_map = {
            "system": "SYSTEM",
            "const": "CONST",
            "eq_ref": "EQ_REF",
            "ref": "INDEX_REF",
            "fulltext": "FULLTEXT",
            "ref_or_null": "REF_OR_NULL",
            "index_merge": "INDEX_MERGE",
            "range": "INDEX_RANGE_SCAN",
            "index": "FULL_INDEX_SCAN",
            "ALL": "FULL_TABLE_SCAN",
        }
        # scan_type must always be a string
        mapped_type = access_type_map.get(access_type)
        scan_type: str = mapped_type if mapped_type else str(access_type).upper()

        # Extract rows
        estimated_rows = plan_data.get("rows")
        if estimated_rows is not None:
            try:
                estimated_rows = int(estimated_rows)
            except (ValueError, TypeError):
                estimated_rows = None

        return ExplainParseResult(
            plan=ExplainPlan(
                plan_text=json.dumps(plan_data, ensure_ascii=False),
                estimated_cost=None,
                estimated_rows=estimated_rows,
                scan_type=scan_type,
                index_name=plan_data.get("key"),
                filter_condition=plan_data.get("Extra"),
            ),
            warnings=["Using traditional EXPLAIN format"],
        )


def _run_explain_postgresql_traditional(conn, bound_sql: str) -> ExplainParseResult:
    """Fallback PostgreSQL EXPLAIN parser for text format."""
    explain_sql = f"EXPLAIN (COSTS, FORMAT TEXT) {bound_sql}"

    with conn.cursor() as cursor:
        cursor.execute(explain_sql)
        rows = cursor.fetchall()

        plan_lines = [str(row[0]) for row in rows]
        plan_text = "\n".join(plan_lines)

        # Try to extract basic info from text
        scan_type = "UNKNOWN"
        estimated_cost = None
        estimated_rows = None

        for line in plan_lines:
            # Extract scan type
            if "Seq Scan" in line:
                scan_type = "FULL_TABLE_SCAN"
            elif "Index Scan" in line:
                scan_type = "INDEX_SCAN"
            elif "Index Only Scan" in line:
                scan_type = "INDEX_ONLY_SCAN"
            elif "Bitmap" in line:
                scan_type = "BITMAP_SCAN"

            # Extract cost and rows from format "cost=X.XX..Y.YY rows=Z width=W"
            cost_match = re.search(r"cost=\d+\.?\d*\.\.(\d+\.?\d*)", line)
            if cost_match:
                try:
                    estimated_cost = float(cost_match.group(1))
                except ValueError:
                    pass

            rows_match = re.search(r"rows=(\d+)", line)
            if rows_match:
                try:
                    estimated_rows = int(rows_match.group(1))
                except ValueError:
                    pass

        return ExplainParseResult(
            plan=ExplainPlan(
                plan_text=plan_text,
                estimated_cost=estimated_cost,
                estimated_rows=estimated_rows,
                scan_type=scan_type,
            ),
            warnings=["Using traditional EXPLAIN format"],
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
            explain_result = _run_explain(conn, db_platform, sql, params)
            plan = explain_result.plan
            rows_returned, exec_time = _execute_and_measure(
                conn, sql, params, db_platform
            )

            # Use actual execution time from EXPLAIN ANALYZE if available
            actual_exec_time = plan.actual_total_time_ms

            return BaselineResult(
                sql_key=sql_key,
                execution_time_ms=exec_time,
                rows_examined=plan.estimated_rows or rows_returned,
                rows_returned=rows_returned,
                explain_plan={
                    "plan_text": plan.plan_text,
                    "scan_type": plan.scan_type,
                    "estimated_cost": plan.estimated_cost,
                    "estimated_rows": plan.estimated_rows,
                    "actual_rows": plan.actual_rows,
                    "actual_total_time_ms": plan.actual_total_time_ms,
                    "index_name": plan.index_name,
                    "filter_condition": plan.filter_condition,
                    # PostgreSQL specific
                    "shared_read_blocks": plan.shared_read_blocks,
                    "shared_hit_blocks": plan.shared_hit_blocks,
                    # MySQL specific
                    "query_cost": plan.query_cost,
                    "used_columns": plan.used_columns,
                },
                database_platform=db_platform,
                sample_params=params,
                actual_execution_time_ms=actual_exec_time,
                buffer_hit_count=plan.shared_hit_blocks,
                buffer_read_count=plan.shared_read_blocks,
                index_used=plan.index_name,
            )
        except Exception as e:
            # Return a "failed" result for this SQL but don't crash the batch
            return BaselineResult(
                sql_key=sql_key,
                execution_time_ms=0,
                rows_examined=0,
                rows_returned=0,
                explain_plan={
                    "scan_type": "ERROR",
                    "error_message": str(e),
                },
                database_platform=db_platform or "unknown",
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
            # Extended metrics
            "actualExecutionTimeMs": r.actual_execution_time_ms,
            "bufferHitCount": r.buffer_hit_count,
            "bufferReadCount": r.buffer_read_count,
            "indexUsed": r.index_used,
        }
        for r in results
    ]
