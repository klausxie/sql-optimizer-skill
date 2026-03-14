"""
Branch Command Module

Provides branch diagnosis functionality for SQL optimization.
Executes EXPLAIN plans to analyze query branches without running full baseline tests.
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
from sqlopt.scripting.fragment_registry import FragmentRegistry, build_fragment_registry
from sqlopt.adapters.branch_diagnose import diagnose_branches


def parse_mapper_xml(file_path: str) -> dict:
    """解析单个 XML 文件的 SQL 语句"""
    import xml.etree.ElementTree as ET

    tree = ET.parse(file_path)
    root = tree.getroot()
    namespace = {"m": "http://mybatis.org/schema/mybatis-3-mapper"}
    mapper_namespace = str(root.attrib.get("namespace") or "").strip()

    results = {}
    for stmt_type in ["select", "insert", "update", "delete"]:
        for elem in root.findall(f".//m:{stmt_type}", namespace):
            stmt_id = elem.get("id")
            if stmt_id:
                results[stmt_id] = {
                    "id": stmt_id,
                    "type": stmt_type,
                    "namespace": mapper_namespace,
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
                    "namespace": mapper_namespace,
                    "template_sql": ET.tostring(elem, encoding="unicode"),
                }

    return results


def process_single_sql(
    sql_id: str,
    sql_unit: dict,
    config: dict,
    fragment_registry: FragmentRegistry | None = None,
) -> dict:
    """处理单个 SQL 语句，生成分支诊断结果"""
    # 构建 fragment registry
    builder = XMLScriptBuilder(
        fragment_registry=fragment_registry,
        default_namespace=sql_unit.get("namespace"),
    )

    # 解析为 SqlNode
    template_sql = sql_unit["template_sql"]
    sql_node = builder.parse(template_sql)

    # 生成分支
    generator = BranchGenerator(strategy="all_combinations", max_branches=100)
    branches = generator.generate(sql_node)

    # 添加 sqlKey
    for branch in branches:
        branch["sqlKey"] = sql_id

    # 禁用基线测试，只执行 EXPLAIN
    diagnose_config = config.copy()
    if "branch" not in diagnose_config:
        diagnose_config["branch"] = {}
    diagnose_config["branch"]["baseline_testing_enabled"] = False

    # 执行诊断（只执行 EXPLAIN，不执行基线测试）
    diagnosed_branches = diagnose_branches(branches, diagnose_config)

    # 移除 baselineTest 字段（如果存在）
    for branch in diagnosed_branches:
        if "baseline" in branch and "baselineTest" in branch["baseline"]:
            del branch["baseline"]["baselineTest"]

    # 统计
    total_branches = len(diagnosed_branches)
    problematic_branches = sum(
        1 for b in diagnosed_branches if b.get("baseline", {}).get("problematic", False)
    )

    return {
        "sqlId": sql_id,
        "type": sql_unit["type"],
        "totalBranches": total_branches,
        "problematicBranches": problematic_branches,
        "branches": diagnosed_branches,
    }


def cmd_branch(args: argparse.Namespace) -> None:
    """
    Branch command entry point.

    Analyzes SQL statement branches using EXPLAIN plans without running full baseline tests.

    支持三种输入模式：
    1. 单 SQL ID 模式: --file xxx.xml --sql-id yyy
    2. 批量 SQL ID 模式: --file xxx.xml --sql-ids a,b,c
    3. 整个文件模式: --file xxx.xml (处理所有 SELECT 语句)

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
                "baseline_testing_enabled": False,
            },
        }

    config = check_and_prompt_dsn(config, config_path, cli_dsn=args.dsn)

    # 确保基线测试被禁用
    if "branch" not in config:
        config["branch"] = {}
    config["branch"]["baseline_testing_enabled"] = False

    # 解析 XML
    sql_units = parse_mapper_xml(str(xml_file))
    registry_scope = sorted(str(path) for path in xml_file.parent.rglob("*.xml"))
    fragment_registry = build_fragment_registry(registry_scope or [str(xml_file)])

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
        result = process_single_sql(sql_id, sql_unit, config, fragment_registry)
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

    # 统计总体问题分支
    total_branches = sum(r["totalBranches"] for r in results)
    total_problematic = sum(r["problematicBranches"] for r in results)

    tips = _generate_optimization_tips(results)

    print("\n" + "=" * 60)
    print(
        f"[OK] 分支推断完成！发现了 {total_branches} 个分支，{total_problematic} 个有问题。"
    )

    if tips:
        print("\n[TIP] 优化建议：")
        for tip in tips:
            print(f"  • {tip}")
    else:
        print("\n[OK] 所有分支看起来正常，未发现明显问题")

    print("\n[TIP] 下一步：")
    print("  • 基线测试: sqlopt-cli baseline --file <path> --sql-id <id>")
    print("  • 完整优化: sqlopt-cli run --config sqlopt.yml")
    print("=" * 60)


def _print_human_readable(result: dict) -> None:
    """打印人类可读的诊断结果"""
    print("\n" + "=" * 80)
    print(f"SQL ID: {result['sqlId']} (Type: {result['type']})")
    print("=" * 80)

    print(
        f"Total Branches: {result['totalBranches']}, "
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
            elif baseline.get("error"):
                tips.append(
                    f"[{sql_id}#{branch_id}] EXPLAIN 失败: {baseline['error'][:50]}"
                )

    return tips


def add_branch_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """
    Add branch subcommand to the CLI parser.

    Args:
        subparsers: The subparsers action from the parent parser

    Returns:
        The configured argument parser for the branch command
    """
    p_branch = subparsers.add_parser(
        "branch",
        help="诊断 SQL 分支（EXPLAIN 计划分析）",
        description=(
            "分析 SQL 语句的分支，生成 EXPLAIN 计划分析。\n"
            "不执行实际基线测试，用于快速诊断查询性能问题。"
        ),
        epilog=(
            "示例:\n"
            "  sqlopt-cli branch --file /path/to/mapper.xml\n"
            "  sqlopt-cli branch --file /path/to/mapper.xml --sql-id listUsers\n"
            "  sqlopt-cli branch --file /path/to/mapper.xml --sql-ids listUsers,findUsers\n"
            "  sqlopt-cli branch --file /path/to/mapper.xml --human-readable\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p_branch.add_argument(
        "--file",
        type=str,
        required=True,
        help="MyBatis mapper XML 文件路径",
    )

    p_branch.add_argument(
        "--sql-id",
        type=str,
        help="单个 SQL statement ID",
    )

    p_branch.add_argument(
        "--sql-ids",
        type=str,
        help="逗号分隔的多个 SQL statement ID",
    )

    p_branch.add_argument(
        "--config",
        default="sqlopt.yml",
        help="sqlopt.yml 配置文件路径（默认：./sqlopt.yml）",
    )

    p_branch.add_argument(
        "--human-readable",
        action="store_true",
        help="以人类可读格式输出",
    )

    p_branch.add_argument(
        "--dsn",
        dest="dsn",
        help="数据库连接字符串（覆盖配置文件中的 db.dsn）",
    )

    p_branch.set_defaults(func=cmd_branch)

    return p_branch


# Standalone execution support
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="sqlopt-cli branch")
    add_branch_parser(parser.add_subparsers(dest="cmd", required=True))
    args = parser.parse_args()
    cmd_branch(args)
