"""
分支诊断模块 - 在 Scan 阶段收集每个分支的 EXPLAIN 和基线性能数据

注意：baseline 模块使用延迟导入，如果模块不存在会自动降级跳过基线测试。
"""

from typing import Any, Optional


def _get_platform_functions(config: dict[str, Any]):
    """Get the appropriate platform functions based on config."""
    platform = config.get("db", {}).get("platform", "").lower()
    if platform == "mysql":
        from ..platforms.mysql.evidence import (
            _collect_explain as mysql_collect_explain,
            _collect_metadata as mysql_collect_metadata,
        )

        return mysql_collect_explain, mysql_collect_metadata
    else:
        from ..platforms.postgresql.evidence import (
            _collect_explain as pg_collect_explain,
            _collect_metadata as pg_collect_metadata,
        )

        return pg_collect_explain, pg_collect_metadata


# Baseline modules - 延迟导入以避免模块缺失导致崩溃
# 详见 _run_baseline_test() 函数


def diagnose_branch(branch: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """诊断单个分支"""
    sql = branch.get("sql", "")
    if not sql:
        return branch

    # 获取配置
    branch_cfg = config.get("branch", {})
    run_actual = branch_cfg.get("run_actual", False)  # 是否实际执行
    baseline_testing_enabled = branch_cfg.get("baseline_testing_enabled", True)
    is_select = sql.strip().upper().startswith("SELECT")

    # Get platform-specific functions
    collect_explain, collect_metadata = _get_platform_functions(config)

    # 执行 EXPLAIN（所有SQL都可以）
    explain_result = collect_explain(config, sql)
    baseline = _parse_explain_plan(explain_result)

    # 执行基线测试（仅 SELECT 且启用）
    if baseline_testing_enabled and is_select:
        baseline_test_result = _run_baseline_test(branch, config, sql)
        if baseline_test_result:
            baseline["baselineTest"] = baseline_test_result

    # 实际执行（仅 SELECT，且用户开启）
    if run_actual and is_select:
        actual_metrics = _run_actual_execution(config, sql)
        baseline["actualMetrics"] = actual_metrics

    # 添加到分支
    branch["baseline"] = baseline

    return branch


def diagnose_branches(
    branches: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """诊断所有分支"""
    for branch in branches:
        diagnose_branch(branch, config)
    return branches


def _parse_explain_plan(explain_result: dict[str, Any]) -> dict[str, Any]:
    """解析 EXPLAIN 结果，提取基线性能数据"""
    if not explain_result.get("ok"):
        return {
            "error": explain_result.get("error", "unknown"),
            "executionTime": None,
            "rowsExamined": None,
            "rowsReturned": None,
            "usingIndex": None,
            "type": None,
        }

    plan_lines = explain_result.get("planLines", [])
    if not plan_lines:
        return {
            "executionTime": None,
            "rowsExamined": None,
            "rowsReturned": None,
            "usingIndex": False,
            "type": "UNKNOWN",
        }

    # 解析关键指标
    plan_text = "\n".join(plan_lines)

    # 估算扫描行数
    rows_examined = _extract_rows(plan_text, "rows")
    rows_returned = _extract_rows(plan_text, "actual rows")

    # 判断是否使用索引
    using_index = any(
        keyword in plan_text.lower()
        for keyword in ["index", "idx_", "primary key", "unique"]
    )

    # 判断扫描类型
    scan_type = _extract_scan_type(plan_text)

    # 估算执行时间（如果有 ANALYZE）
    execution_time = _extract_time(plan_text)

    return {
        "executionTime": execution_time,
        "rowsExamined": rows_examined,
        "rowsReturned": rows_returned,
        "usingIndex": using_index,
        "type": scan_type,
        "planLines": plan_lines[:10],  # 保留前10行
        "problematic": scan_type in ["ALL", "FSEQ"],  # 标记问题
    }


def _extract_rows(plan_text: str, prefix: str) -> int | None:
    """提取行数"""
    import re

    pattern = rf"{prefix}\s*:\s*(\d+)"
    matches = re.findall(pattern, plan_text, re.IGNORECASE)
    if matches:
        return max(int(m) for m in matches)
    return None


def _extract_time(plan_text: str) -> str | None:
    """提取执行时间"""
    import re

    pattern = r"actual time=(\d+\.?\d*)\.\.(\d+\.?\d*)"
    matches = re.findall(pattern, plan_text, re.IGNORECASE)
    if matches:
        # 取最大值作为总时间
        total = max(float(m[1]) for m in matches)
        return f"{total:.2f}ms"
    return None


def _extract_scan_type(plan_text: str) -> str:
    """提取扫描类型"""
    plan_lower = plan_text.lower()

    if "seq scan" in plan_lower:
        return "ALL"  # 全表扫描
    elif "index scan" in plan_lower:
        return "IDX_SCAN"
    elif "index only scan" in plan_lower:
        return "IDX_ONLY"
    elif "bitmap heap scan" in plan_lower:
        return "BITMAP"
    elif "function scan" in plan_lower or "table function" in plan_lower:
        return "FUNC"
    elif "foreign scan" in plan_lower:
        return "FOREIGN"
    else:
        return "OTHER"


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


def _run_actual_execution(config: dict[str, Any], sql: str) -> dict[str, Any]:
    """实际执行 SQL（仅 SELECT）"""
    from ..platforms.mysql.evidence import _get_sql_connect

    db_cfg = config.get("db", {})
    dsn = db_cfg.get("dsn")
    if not dsn:
        return {"error": "dsn_not_set"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"error": "db_driver_not_installed"}

    # 准备参数
    prepared_sql = sql.replace("?", "NULL")  # 用 NULL 作为参数

    timeout_ms = int(db_cfg.get("statement_timeout_ms", 3000))

    is_mysql = driver in ("pymysql", "mysql-connector")
    conn = None

    try:
        import time

        start_time = time.time()

        if is_mysql:
            db_config = _parse_dsn(dsn)
            conn = connect(
                host=db_config.get("host"),
                port=db_config.get("port", 3306),
                user=db_config.get("user"),
                password=db_config.get("password"),
                database=db_config.get("database"),
            )
            cur = conn.cursor()
            cur.execute(prepared_sql)
            rows = cur.fetchall()
            execution_time_ms = (time.time() - start_time) * 1000

            cur.close()
            conn.close()

            return {
                "executionTime": f"{execution_time_ms:.2f}ms",
                "rowsReturned": len(rows),
                "executed": True,
            }
        else:
            with connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SET statement_timeout = {max(1, timeout_ms)}")
                    cur.execute(prepared_sql)
                    rows = cur.fetchall()
                    execution_time_ms = (time.time() - start_time) * 1000

                    return {
                        "executionTime": f"{execution_time_ms:.2f}ms",
                        "rowsReturned": len(rows),
                        "executed": True,
                    }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return {"error": str(e), "executed": False}


def _extract_table_names(sql: str) -> list[str]:
    """Extract table names from SQL using simple pattern matching."""
    import re

    tables = []
    sql_upper = sql.upper()

    from_pattern = r"FROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)"
    for match in re.finditer(from_pattern, sql_upper):
        table = match.group(1)
        tables.append(table.lower())

    join_pattern = r"JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)"
    for match in re.finditer(join_pattern, sql_upper):
        table = match.group(1)
        if table.lower() not in [t.lower() for t in tables]:
            tables.append(table.lower())

    return tables


def _run_baseline_test(
    branch: dict[str, Any], config: dict[str, Any], sql: str
) -> Optional[dict[str, Any]]:
    """Run baseline testing for a branch.

    This function performs parameter parsing, data sampling, parameter binding,
    performance collection, and report generation.

    Note: Uses lazy imports for baseline modules. If modules don't exist,
    gracefully returns None to skip baseline testing.

    Returns:
        Baseline test result dict or None if failed or modules unavailable.
    """
    # 延迟导入 baseline 模块
    try:
        from ..baseline.parameter_parser import parse_parameters
        from ..baseline.data_sampler import sample_table_data
        from ..baseline.type_extractor import extract_column_types
        from ..baseline.parameter_binder import bind_parameters
        from ..baseline.performance_collector import collect_performance
        from ..baseline.reporter import generate_baseline_report
    except ImportError:
        # Baseline 模块不可用，静默跳过
        return None

    try:
        params = parse_parameters(sql)
        if not params:
            return None

        tables = _extract_table_names(sql)
        if not tables:
            return None

        table_name = tables[0]
        data_rows = sample_table_data(config, table_name, limit=10)
        if not data_rows:
            return None

        column_types = extract_column_types(config, table_name)
        if not column_types:
            column_types = {}

        bound_params_list = bind_parameters(params, data_rows, column_types)
        if not bound_params_list:
            return None

        bound_params = bound_params_list[0]

        db_cfg = config.get("db", {})
        timeout_ms = int(db_cfg.get("statement_timeout_ms", 3000))

        performance_metrics = collect_performance(
            config=config,
            sql=sql,
            bound_params=bound_params,
            runs=5,
            timeout_ms=timeout_ms,
        )

        sql_unit = {
            "sqlKey": branch.get("sqlKey", "unknown"),
            "parameters": [{"name": k, "value": v} for k, v in bound_params.items()],
        }

        report = generate_baseline_report(performance_metrics, sql_unit)

        return {
            "report": report,
            "performanceMetrics": performance_metrics,
            "sampled": True,
        }

    except Exception:
        return None


def collect_diagnostic_info(
    sql_unit: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """收集完整的诊断信息"""
    branches = sql_unit.get("branches", [])

    # 收集表结构信息
    template_sql = sql_unit.get("sql", "")
    _, collect_metadata = _get_platform_functions(config)
    metadata = collect_metadata(config, template_sql)

    # 诊断每个分支
    branches = diagnose_branches(branches, config)

    # 统计问题分支
    problem_branches = [
        b for b in branches if b.get("baseline", {}).get("problematic", False)
    ]

    return {
        "sqlKey": sql_unit.get("sqlKey"),
        "totalBranches": len(branches),
        "problemBranches": len(problem_branches),
        "metadata": metadata,
        "branches": branches,
    }
