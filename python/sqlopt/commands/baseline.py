"""
Baseline Command Module

Provides baseline data collection and comparison functionality for SQL optimization.
"""

import sys

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass  # Fallback to default if reconfigure not available

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from sqlopt import config as cfg_module
from sqlopt.commands.dsn_input import check_and_prompt_dsn
from sqlopt.scripting.xml_script_builder import XMLScriptBuilder
from sqlopt.scripting.branch_generator import BranchGenerator
from sqlopt.scripting.fragment_registry import FragmentRegistry
from sqlopt.adapters.branch_diagnose import diagnose_branches


def parse_mapper_xml(file_path: str) -> dict:
    """解析单个 XML 文件的 SQL 语句"""
    import xml.etree.ElementTree as ET

    tree = ET.parse(file_path)
    root = tree.getroot()
    namespace = {"m": "http://mybatis.org/schema/mybatis-3-mapper"}

    results = {}
    for stmt_type in ["select", "insert", "update", "delete"]:
        for elem in root.findall(f".//m:{stmt_type}", namespace):
            stmt_id = elem.get("id")
            if stmt_id:
                results[stmt_id] = {
                    "id": stmt_id,
                    "type": stmt_type,
                    "template_sql": ET.tostring(elem, encoding="unicode"),
                }

    # 无命名空间
    for stmt_type in ["select", "insert", "update", "delete"]:
        for elem in root.findall(f".//{stmt_type}"):
            stmt_id = elem.get("id")
            if stmt_id and stmt_id not in results:
                results[stmt_id] = {
                    "id": stmt_id,
                    "type": stmt_type,
                    "template_sql": ET.tostring(elem, encoding="unicode"),
                }

    return results


def process_single_sql(
    sql_id: str,
    sql_unit: dict,
    config: dict,
) -> dict:
    """处理单个 SQL 语句，生成基线结果"""
    # 构建 fragment registry
    fragment_registry = FragmentRegistry()
    builder = XMLScriptBuilder(fragment_registry=fragment_registry)

    # 解析为 SqlNode
    template_sql = sql_unit["template_sql"]
    sql_node = builder.parse(template_sql)

    # 生成分支
    generator = BranchGenerator(strategy="all_combinations", max_branches=100)
    branches = generator.generate(sql_node)

    # 添加 sqlKey
    for branch in branches:
        branch["sqlKey"] = sql_id

    # 执行诊断
    diagnosed_branches = diagnose_branches(branches, config)

    # 统计
    total_branches = len(diagnosed_branches)
    baseline_executed = sum(
        1
        for b in diagnosed_branches
        if "baseline" in b and b["baseline"].get("baselineTest")
    )
    baseline_failed = sum(
        1
        for b in diagnosed_branches
        if "baseline" in b
        and (
            b["baseline"].get("error")
            or (
                b.get("sql", "").strip().upper().startswith("SELECT")
                and not b["baseline"].get("baselineTest")
            )
        )
    )
    problematic_branches = sum(
        1 for b in diagnosed_branches if b.get("baseline", {}).get("problematic", False)
    )

    return {
        "sqlId": sql_id,
        "type": sql_unit["type"],
        "totalBranches": total_branches,
        "baselineExecuted": baseline_executed,
        "baselineFailed": baseline_failed,
        "problematicBranches": problematic_branches,
        "branches": diagnosed_branches,
    }


def cmd_baseline(args: argparse.Namespace) -> None:
    """
    Baseline command entry point.

    Collects baseline performance data for SQL statements and prepares for comparison.

    支持三种输入模式：
    1. 单 SQL ID 模式: --file xxx.xml --sql-id yyy
    2. 批量 SQL ID 模式: --file xxx.xml --sql-ids a,b,c
    3. 整个文件模式: --file xxx.xml (处理所有 SQL，只对 SELECT 执行基线)

    Args:
        args: Parsed command-line arguments (Namespace object)

    Returns:
        None

    Raises:
        SystemExit: On error conditions
    """
    # 验证参数
    if not args.file:
        print("Error: --file is required", file=sys.stderr)
        sys.exit(1)

    xml_file = Path(args.file)
    if not xml_file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # 加载配置
    config_path = args.config or "sqlopt.yml"
    try:
        config = cfg_module.load_config(Path(config_path))
    except Exception as e:
        print(
            f"Warning: Failed to load config from {config_path}: {e}", file=sys.stderr
        )
        config = {
            "db": {
                "platform": "postgresql",
                "dsn": "postgresql://postgres:postgres@localhost:5432/postgres",
            },
            "branch": {
                "baseline_testing_enabled": True,
            },
        }

    config = check_and_prompt_dsn(config, config_path, cli_dsn=args.dsn)

    # 解析 XML
    sql_units = parse_mapper_xml(str(xml_file))

    if not sql_units:
        print(f"Warning: No SQL statements found in {args.file}", file=sys.stderr)
        print("[]")
        return

    # 确定处理模式
    target_sql_ids: Optional[list[str]] = None

    if args.sql_id:
        # 单 SQL ID 模式
        target_sql_ids = [args.sql_id]
    elif args.sql_ids:
        # 批量 SQL ID 模式
        target_sql_ids = [s.strip() for s in args.sql_ids.split(",") if s.strip()]
    else:
        # 整个文件模式 - 只处理 SELECT
        target_sql_ids = [
            sql_id for sql_id, unit in sql_units.items() if unit["type"] == "select"
        ]

    # 验证目标 SQL IDs
    invalid_ids = [sid for sid in target_sql_ids if sid not in sql_units]
    if invalid_ids:
        print(
            f"Error: SQL ID(s) not found in file: {invalid_ids}",
            file=sys.stderr,
        )
        print(f"  Available SQL IDs: {list(sql_units.keys())}", file=sys.stderr)
        sys.exit(1)

    # 处理每个 SQL
    results = []
    for sql_id in target_sql_ids:
        sql_unit = sql_units[sql_id]
        result = process_single_sql(sql_id, sql_unit, config)
        results.append(result)

    # 输出 JSON
    output = {
        "file": str(xml_file),
        "totalStatements": len(results),
        "results": results,
    }

    if args.human_readable:
        # 人类可读格式
        for result in results:
            _print_human_readable(result)
    else:
        # JSON 格式
        print(json.dumps(output, indent=2, ensure_ascii=False))

    tips = _generate_optimization_tips(results)
    total_branches = sum(r["totalBranches"] for r in results)
    total_baseline_executed = sum(r["baselineExecuted"] for r in results)
    total_baseline_failed = sum(r["baselineFailed"] for r in results)
    total_problematic = sum(r["problematicBranches"] for r in results)

    print("\n" + "=" * 60)

    if total_baseline_failed > 0:
        print(
            f"[WARN] 基线收集完成！静态分析: {total_branches} 分支, "
            f"数据库执行失败: {total_baseline_failed}, "
            f"成功执行: {total_baseline_executed}, "
            f"有问题: {total_problematic}"
        )
    elif total_baseline_executed == 0 and total_branches > 0:
        print(
            f"[INFO] 静态分析完成！分析了 {total_branches} 个分支，"
            f"未进行数据库基线测试 (可能未启用或非SELECT语句)"
        )
    else:
        print(
            f"[OK] 基线收集完成！分析了 {total_branches} 个分支，"
            f"成功执行: {total_baseline_executed}, 有问题: {total_problematic}"
        )

    if tips:
        print("\n[TIP] 优化建议：")
        for tip in tips:
            print(f"  • {tip}")
    elif total_baseline_failed == 0 and total_baseline_executed > 0:
        print("\n[OK] 所有分支看起来正常，未发现明显问题")

    print("\n[TIP] 下一步：")
    print("  • 完整优化: sqlopt-cli run --config sqlopt.yml")
    print("=" * 60)


def _print_human_readable(result: dict) -> None:
    """打印人类可读的基线结果"""
    print("\n" + "=" * 80)
    print(f"SQL ID: {result['sqlId']} (Type: {result['type']})")
    print("=" * 80)

    print(
        f"Total Branches: {result['totalBranches']}, "
        f"Baseline Executed: {result['baselineExecuted']}, "
        f"Baseline Failed: {result['baselineFailed']}, "
        f"Problematic: {result['problematicBranches']}"
    )

    branches = result.get("branches", [])
    if not branches:
        print("  No branch data")
        return

    # 表格头
    print("\n" + "-" * 80)
    print(
        f"{'Branch ID':<12} {'扫描类型':<12} {'执行时间':<15} {'扫描行数':<15} {'返回行数':<15}"
    )
    print("-" * 80)

    for branch in branches:
        bid = branch.get("branch_id", "?")
        baseline = branch.get("baseline", {})

        scan_type = baseline.get("type") or "N/A"
        exec_time = baseline.get("executionTime") or "N/A"
        rows_examined = baseline.get("rowsExamined") or "N/A"
        rows_returned = baseline.get("rowsReturned") or "N/A"

        print(
            f"{bid:<12} {scan_type:<12} {str(exec_time):<15} {str(rows_examined):<15} {str(rows_returned):<15}"
        )

    print("-" * 80)


def _generate_optimization_tips(results: list[dict]) -> list[str]:
    for result in results:
        for branch in result.get("branches", []):
            baseline = branch.get("baseline", {})
            if baseline.get("error"):
                print("跳过 - 数据库执行失败，无性能数据")
                return []

    tips = []

    for result in results:
        sql_id = result.get("sqlId", "unknown")
        for branch in result.get("branches", []):
            branch_id = branch.get("branch_id", "?")
            baseline = branch.get("baseline", {})

            scan_type = baseline.get("type", "UNKNOWN")
            using_index = baseline.get("usingIndex", False)
            rows_examined = baseline.get("rowsExamined")

            if scan_type == "ALL":
                tips.append(f"[{sql_id}#{branch_id}] 全表扫描 (type=ALL)，建议添加索引")
            elif scan_type == "index" and rows_examined and rows_examined > 1000:
                tips.append(f"[{sql_id}#{branch_id}] 索引全扫描，检查索引选择性")
            elif not using_index and scan_type not in ["UNKNOWN", None]:
                tips.append(f"[{sql_id}#{branch_id}] 未使用索引，考虑优化 WHERE 条件")

    return tips


def add_baseline_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """
    Add baseline subcommand to the CLI parser.

    Args:
        subparsers: The subparsers action from the parent parser

    Returns:
        The configured argument parser for the baseline command
    """
    p_baseline = subparsers.add_parser(
        "baseline",
        help="Collect baseline performance data",
        description=(
            "Collect baseline performance data for SQL statements.\n"
            "Used for comparing optimization results."
        ),
        epilog=(
            "示例:\n"
            "  sqlopt-cli baseline --file /path/to/statements.jsonl\n"
            "  sqlopt-cli baseline --sql-id searchUsersAdvanced\n"
            "  sqlopt-cli baseline --sql-ids searchUsersAdvanced,patchUserStatusAdvanced\n"
            "  sqlopt-cli baseline --config sqlopt.yml --human-readable\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p_baseline.add_argument(
        "--file",
        type=str,
        help="Input file containing SQL statements (JSONL format)",
    )

    p_baseline.add_argument(
        "--sql-id",
        type=str,
        help="Single SQL statement ID to process",
    )

    p_baseline.add_argument(
        "--sql-ids",
        type=str,
        help="Comma-separated list of SQL statement IDs to process",
    )

    p_baseline.add_argument(
        "--config",
        default="sqlopt.yml",
        help="sqlopt.yml 配置文件路径（默认：./sqlopt.yml）",
    )

    p_baseline.add_argument(
        "--human-readable",
        action="store_true",
        help="Output results in human-readable format instead of JSON",
    )

    p_baseline.add_argument(
        "--dsn",
        dest="dsn",
        help="数据库连接字符串（覆盖配置文件中的 db.dsn）",
    )

    p_baseline.set_defaults(func=cmd_baseline)

    return p_baseline


# Standalone execution support
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="sqlopt-cli baseline")
    add_baseline_parser(parser.add_subparsers(dest="cmd", required=True))
    args = parser.parse_args()
    cmd_baseline(args)
