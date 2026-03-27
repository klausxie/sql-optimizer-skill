"""Summary generator for stage execution reports.

This module provides utilities for generating human-readable SUMMARY.md content
from stage execution data. It does NOT perform file I/O - it only generates text.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput


def truncate_text(text: str, max_chars: int = 1024) -> str:
    """Truncate text to a maximum number of characters.

    Args:
        text: The text to truncate.
        max_chars: Maximum number of characters (default: 1024).

    Returns:
        Truncated text with "... (truncated)" suffix if longer than max_chars,
        otherwise the original text.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (truncated)"


def extract_table_names_from_sql(sql_text: str) -> List[str]:
    """Extract table names from SQL text by parsing FROM and JOIN clauses.

    Args:
        sql_text: SQL text to parse.

    Returns:
        List of table names found in the SQL text.
    """
    import re

    if not sql_text:
        return []

    patterns = [
        r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+AS\s+[a-zA-Z_][a-zA-Z0-9_]*)?",
        r"\b(?:INNER|LEFT|RIGHT|OUTER|CROSS)?\s*JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    ]

    table_names: set[str] = set()
    sql_upper = sql_text.upper()

    for pattern in patterns:
        matches = re.finditer(pattern, sql_upper, re.IGNORECASE)
        for match in matches:
            table_name = match.group(1)
            if table_name and table_name.upper() not in (
                "SELECT",
                "WHERE",
                "ON",
                "AND",
                "OR",
                "NOT",
                "IN",
                "SET",
            ):
                table_names.add(match.group(1).lower())

    return list(table_names)


def generate_init_summary_markdown(
    output: InitOutput,
    duration_seconds: float,
    files_count: int,
    file_size_bytes: int,
    schema_extraction_success: bool = True,
    field_distributions_count: int = 0,
) -> str:
    """Generate a valuable INIT stage SUMMARY with actual extracted data.

    Args:
        output: InitOutput containing extracted SQL units, fragments, schemas.
        duration_seconds: Total execution time in seconds.
        files_count: Number of mapper files processed.
        file_size_bytes: Total size of output files in bytes.
        schema_extraction_success: Whether schema extraction succeeded.
        field_distributions_count: Number of field distributions collected.

    Returns:
        Markdown-formatted SUMMARY.md with actionable insights.
    """
    lines: List[str] = []

    lines.append("# INIT 阶段报告")
    lines.append("")
    lines.append(f"**运行ID:** `{output.run_id}`")
    lines.append(f"**耗时:** {duration_seconds:.2f} 秒")
    lines.append("")

    # Statement type breakdown
    type_counter: Counter = Counter()
    for unit in output.sql_units:
        type_counter[unit.statement_type] += 1

    lines.append("## SQL类型分布")
    lines.append("")
    type_colors = {
        "SELECT": "🟢",
        "INSERT": "🔵",
        "UPDATE": "🟡",
        "DELETE": "🔴",
    }
    for stmt_type in sorted(type_counter.keys()):
        icon = type_colors.get(stmt_type, "⚪")
        lines.append(f"- {icon} **{stmt_type}**: {type_counter[stmt_type]} 条")
    lines.append("")

    # Mapper file overview
    if output.xml_mappings:
        lines.append("## Mapper文件概览")
        lines.append("")
        lines.append("| 文件 | 语句数 | 片段数 |")
        lines.append("|------|---------|--------|")
        for fm in output.xml_mappings.files:
            stmt_count = len(fm.statements)
            frag_count = len(fm.fragments)
            filename = fm.xml_path.split("/")[-1]
            lines.append(f"| `{filename}` | {stmt_count} | {frag_count} |")
        lines.append("")

    # SQL units grouped by mapper
    lines.append("## SQL单元列表")
    lines.append("")
    units_by_file: Dict[str, List[Tuple[str, str]]] = {}
    for unit in output.sql_units:
        if unit.mapper_file not in units_by_file:
            units_by_file[unit.mapper_file] = []
        units_by_file[unit.mapper_file].append((unit.sql_id, unit.statement_type))

    for mapper_file, units in sorted(units_by_file.items()):
        filename = mapper_file.split("/")[-1]
        lines.append(f"### `{filename}`")
        lines.append("")
        for sql_id, stmt_type in units:
            icon = type_colors.get(stmt_type, "⚪")
            lines.append(f"- {icon} `{sql_id}`")
        lines.append("")

    # Table references
    all_tables: set = set()
    for unit in output.sql_units:
        tables = extract_table_names_from_sql(unit.sql_text)
        all_tables.update(tables)

    if all_tables:
        lines.append("## 表引用")
        lines.append("")
        lines.append(f"共涉及 **{len(all_tables)}** 张表:")
        lines.append("")
        for table in sorted(all_tables):
            lines.append(f"- `{table}`")
        lines.append("")

    # Fragment usage
    if output.sql_fragments:
        lines.append("## SQL片段")
        lines.append("")
        lines.append(f"发现 **{len(output.sql_fragments)}** 个可复用片段:")
        lines.append("")
        for frag in output.sql_fragments[:10]:
            filename = frag.xml_path.split("/")[-1] if frag.xml_path else "unknown"
            lines.append(f"- `{frag.fragment_id}` @ `{filename}`:{frag.start_line}")
        if len(output.sql_fragments) > 10:
            lines.append(f"- ... 还有 {len(output.sql_fragments) - 10} 个片段")
        lines.append("")

    # Schema extraction status
    lines.append("## Schema提取状态")
    lines.append("")
    if output.table_schemas:
        lines.append(f"✅ 成功提取 **{len(output.table_schemas)}** 个表的Schema")
        for table_name in sorted(list(output.table_schemas.keys())[:5]):
            cols = len(output.table_schemas[table_name].columns)
            lines.append(f"  - `{table_name}`: {cols} 列")
        if len(output.table_schemas) > 5:
            lines.append(f"  - ... 还有 {len(output.table_schemas) - 5} 张表")
    else:
        if schema_extraction_success:
            lines.append("⚠️ 未提取到表Schema（请检查数据库连接配置）")
        else:
            lines.append("ℹ️ 表Schema提取已跳过（无数据库连接）")
    lines.append("")

    # Field distribution status
    if field_distributions_count > 0:
        lines.append("## WHERE字段分布")
        lines.append("")
        lines.append(f"✅ 已收集 **{field_distributions_count}** 个WHERE字段的数据分布")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| WHERE字段分布 | {field_distributions_count} |")
        lines.append("")

    # Parse strategy suggestions based on condition complexity
    lines.append("## Parse Strategy Suggestions")
    lines.append("")
    lines.append("| SQL Unit | Conditions | Suggested Strategy |")
    lines.append("|----------|------------|-------------------|")

    def _count_conditions(sql_text: str) -> int:
        """Count <if test=\"...\"> patterns in SQL text."""
        import re

        if_pattern = r'<if\s+test\s*=\s*["\']([^"\']+)["\']'
        return len(re.findall(if_pattern, sql_text, re.IGNORECASE))

    def _suggest_strategy(cond_count: int) -> str:
        """Suggest parse strategy based on condition count."""
        if cond_count <= 3:
            return "all_combinations"
        elif cond_count <= 8:
            return "ladder"
        else:
            return "pairwise"

    for unit in output.sql_units[:20]:  # Limit to first 20 for readability
        cond_count = _count_conditions(unit.sql_text)
        suggested = _suggest_strategy(cond_count)
        lines.append(f"| `{unit.sql_id}` | {cond_count} | {suggested} |")

    if len(output.sql_units) > 20:
        lines.append(f"| ... | ... | ... (还有 {len(output.sql_units) - 20} 个SQL单元) |")
    lines.append("")

    # Statistics summary
    lines.append("## 统计信息")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| Mapper文件 | {files_count} |")
    lines.append(f"| SQL单元 | {len(output.sql_units)} |")
    lines.append(f"| SQL片段 | {len(output.sql_fragments)} |")
    lines.append(f"| 表引用 | {len(all_tables)} |")
    lines.append(f"| Schema表 | {len(output.table_schemas)} |")
    lines.append(f"| 输出大小 | {file_size_bytes:,} 字节 |")
    lines.append("")

    lines.append("---")
    lines.append("*由 SQL Optimizer 生成 - INIT 阶段*")

    result = "\n".join(lines)

    max_output_size = 50 * 1024
    if len(result) > max_output_size:
        result = result[:max_output_size] + "\n\n... (output truncated to 50KB)"

    return result


@dataclass
class StageSummary:
    """Summary data for a stage execution.

    Attributes:
        stage_name: Name of the pipeline stage (e.g., "init", "parse").
        run_id: Unique identifier for this pipeline run.
        duration_seconds: Total execution time in seconds.
        sql_units_count: Number of SQL units processed.
        branches_count: Number of SQL branches generated.
        files_count: Number of files processed.
        file_size_bytes: Total size of output files in bytes.
        errors: List of error messages encountered.
        warnings: List of warning messages encountered.
    """

    stage_name: str
    run_id: str
    duration_seconds: float
    sql_units_count: int
    branches_count: int
    files_count: int
    file_size_bytes: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


_DATA_CONTRACT_GUIDE = """
## 数据契约说明

本节描述了 SQL 优化器流水线中使用的核心数据结构。

### SQL单元 (SQLUnit)

**SQL单元** 表示从 MyBatis XML mapper 文件中提取的单个 SQL 语句。

| 字段 | 类型 | 描述 |
|------|------|------|
| id | str | SQL单元的唯一标识符 |
| mapper_file | str | 源 XML mapper 文件路径 |
| sql_id | str | XML statement 标签的 `id` 属性 |
| sql_text | str | 保留 MyBatis 标签的原始 SQL 文本 |
| statement_type | str | 类型：SELECT, INSERT, UPDATE, DELETE |

### SQL分支 (SQLBranch)

**SQL分支** 表示已解析动态 MyBatis 标签的 SQL 单元展开版本。

| 字段 | 类型 | 描述 |
|------|------|------|
| path_id | str | 此分支的唯一标识符 |
| condition | str | 激活此分支的可选条件 |
| expanded_sql | str | 动态标签已完全展开的 SQL |
| is_valid | bool | 展开后的 SQL 语法是否有效 |
| risk_flags | list[str] | 在 SQL 中检测到的潜在问题 |
| active_conditions | list[str] | 此分支必须为真的条件 |
| risk_score | float | 计算的风险分数 (0.0 = 安全, 1.0 = 危险) |
| score_reasons | list[str] | 风险分数的解释 |

### 性能基线 (PerformanceBaseline)

**性能基线** 捕获来自数据库的 SQL 执行计划和估计成本。

| 字段 | 类型 | 描述 |
|------|------|------|
| sql_unit_id | str | 源 SQL单元 的引用 |
| path_id | str | 特定 SQL分支 的引用 |
| plan | dict | 数据库执行计划 (EXPLAIN 输出) |
| estimated_cost | float | 计划器的估计执行成本 |
| actual_time_ms | float | 实际执行时间（毫秒，如果可用） |

### 优化建议 (OptimizationProposal)

**优化建议** 表示 LLM 生成的 SQL 性能改进建议。

| 字段 | 类型 | 描述 |
|------|------|------|
| sql_unit_id | str | 源 SQL单元 的引用 |
| path_id | str | 特定 SQL分支 的引用 |
| original_sql | str | 优化前的原始 SQL |
| optimized_sql | str | 建议的优化 SQL |
| rationale | str | 解释此优化如何提供帮助 |
| confidence | float | LLM 置信度分数 (0.0 到 1.0) |
"""


def generate_summary_markdown(summary: StageSummary) -> str:
    """Generate a human-readable SUMMARY.md content from stage summary data.

    Args:
        summary: StageSummary dataclass containing execution statistics.

    Returns:
        Markdown-formatted string suitable for SUMMARY.md file.
        Output is kept under 50KB for readability.
    """
    lines: List[str] = []

    lines.append(f"# {summary.stage_name.upper()} 阶段报告")
    lines.append("")
    lines.append(f"**运行ID:** {summary.run_id}")
    lines.append(f"**耗时:** {summary.duration_seconds:.2f} 秒")
    lines.append("")

    lines.append("## 统计信息")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| SQL单元数 | {summary.sql_units_count} |")
    lines.append(f"| 分支数 | {summary.branches_count} |")
    lines.append(f"| 文件数 | {summary.files_count} |")
    lines.append(f"| 文件大小 | {summary.file_size_bytes:,} 字节 |")
    lines.append("")

    lines.append(_DATA_CONTRACT_GUIDE)

    if summary.errors:
        lines.append("## 错误列表")
        lines.append("")
        for i, error in enumerate(summary.errors, 1):
            lines.append(f"{i}. {truncate_text(error, max_chars=500)}")
        lines.append("")

    if summary.warnings:
        lines.append("## 警告列表")
        lines.append("")
        for i, warning in enumerate(summary.warnings, 1):
            lines.append(f"{i}. {truncate_text(warning, max_chars=500)}")
        lines.append("")

    lines.append("---")
    lines.append(f"*由 SQL Optimizer 生成 - 阶段: {summary.stage_name}*")

    result = "\n".join(lines)

    max_output_size = 50 * 1024
    if len(result) > max_output_size:
        result = result[:max_output_size] + "\n\n... (output truncated to 50KB)"

    return result


def _cost_category(cost: float) -> str:
    """Categorize a cost value into low/medium/high."""
    if cost == 0.0:
        return "unknown"
    if cost < 100.0:
        return "low"
    if cost < 1000.0:
        return "medium"
    return "high"


def _extract_sql_preview(sql: str, max_len: int = 80) -> str:
    """Extract a short preview of a SQL statement."""
    sql = sql.strip()
    if len(sql) <= max_len:
        return sql
    return sql[:max_len] + "..."


def generate_recognition_summary_markdown(
    output: RecognitionOutput,
    duration_seconds: float,
    file_size_bytes: int,
    files_count: int,
) -> str:
    """Generate a valuable RECOGNITION stage SUMMARY with baseline analysis.

    Args:
        output: RecognitionOutput containing all PerformanceBaseline records.
        duration_seconds: Total execution time in seconds.
        file_size_bytes: Total size of output files in bytes.
        files_count: Number of output files written.

    Returns:
        Markdown-formatted SUMMARY.md with actionable insights.
    """
    baselines = output.baselines
    lines: list[str] = []

    lines.append("# RECOGNITION 阶段报告")
    lines.append("")
    lines.append(f"**运行ID:** `{getattr(output, 'run_id', 'unknown')}`")
    lines.append(f"**耗时:** {duration_seconds:.2f} 秒")
    lines.append("")

    # --- Execution overview ---
    total = len(baselines)
    success = sum(1 for b in baselines if b.execution_error is None)
    failed = total - success
    error_rate = (failed / total * 100) if total > 0 else 0.0

    with_plan = sum(1 for b in baselines if b.plan is not None)
    with_time = sum(1 for b in baselines if b.actual_time_ms is not None)
    with_signature = sum(1 for b in baselines if b.result_signature is not None)

    lines.append("## 执行概览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 总分支数 | {total} |")
    lines.append(f"| ✅ 成功 | {success} |")
    lines.append(f"| ❌ 失败 | {failed} |")
    lines.append(f"| 失败率 | {error_rate:.1f}% |")
    lines.append(f"| 有执行计划 | {with_plan} |")
    lines.append(f"| 有实际耗时 | {with_time} |")
    lines.append(f"| 有结果签名 | {with_signature} |")
    lines.append("")

    # --- Cost distribution ---
    costs = [b.estimated_cost for b in baselines if b.estimated_cost > 0]
    if costs:
        cost_min = min(costs)
        cost_max = max(costs)
        cost_avg = sum(costs) / len(costs)

        cost_buckets: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        for b in baselines:
            cat = _cost_category(b.estimated_cost)
            if cat != "unknown":
                cost_buckets[cat] += 1
            elif b.estimated_cost == 0 and b.execution_error is None:
                cost_buckets["unknown"] += 1

        lines.append("## 成本分布")
        lines.append("")
        lines.append("| 成本区间 | 分支数 |")
        lines.append("|----------|--------|")
        lines.append(f"| 🔴 高 (>1000) | {cost_buckets['high']} |")
        lines.append(f"| 🟡 中 (100-1000) | {cost_buckets['medium']} |")
        lines.append(f"| 🟢 低 (<100) | {cost_buckets['low']} |")
        lines.append(f"| ⚪ 未知 (=0) | {cost_buckets['unknown']} |")
        lines.append("")
        lines.append(f"**成本范围:** {cost_min:.2f} ~ {cost_max:.2f}，均值 {cost_avg:.2f}")
        lines.append("")

    # --- Slow branches Top N ---
    valid_branches = [b for b in baselines if b.execution_error is None and b.plan is not None]
    slow_branches = sorted(valid_branches, key=lambda b: b.estimated_cost, reverse=True)[:10]

    if slow_branches:
        lines.append("## 慢分支 Top 10（按 estimated_cost）")
        lines.append("")
        lines.append("| # | SQL Unit | Branch | Cost | Actual(ms) | Rows Returned |")
        lines.append("|---|----------|--------|------|-------------|---------------|")
        for i, b in enumerate(slow_branches, 1):
            actual_ms = f"{b.actual_time_ms:.1f}" if b.actual_time_ms else "-"
            rows_ret = str(b.rows_returned) if b.rows_returned is not None else "-"
            lines.append(
                f"| {i} | `{b.sql_unit_id}` | `{b.path_id}` | {b.estimated_cost:.2f} | {actual_ms} | {rows_ret} |"
            )
        lines.append("")
        lines.append(f"**Top SQL:** `{_extract_sql_preview(slow_branches[0].original_sql, 80)}`")
        lines.append("")

    # --- Branch type distribution ---
    branch_types: dict[str, int] = {}
    for b in baselines:
        bt = b.branch_type or "normal"
        branch_types[bt] = branch_types.get(bt, 0) + 1

    lines.append("## 分支类型分布")
    lines.append("")
    for bt, cnt in sorted(branch_types.items(), key=lambda x: -x[1]):
        icon = "🔴" if bt == "error" else "🔵" if bt == "baseline_only" else "🟢"
        lines.append(f"- {icon} **{bt}**: {cnt} 条")
    lines.append("")

    # --- Per SQL unit summary ---
    units_map: dict[str, list[PerformanceBaseline]] = {}
    for b in baselines:
        if b.sql_unit_id not in units_map:
            units_map[b.sql_unit_id] = []
        units_map[b.sql_unit_id].append(b)

    lines.append(f"## SQL Unit 概览（共 {len(units_map)} 个 Unit）")
    lines.append("")
    lines.append("| Unit | 分支数 | 成功率 | 最高 Cost | 平均 Cost |")
    lines.append("|------|--------|--------|----------|----------|")

    unit_summaries: list[tuple[str, int, str, float, float]] = []
    for unit_id, unit_bs in units_map.items():
        total_branches = len(unit_bs)
        unit_success = sum(1 for b in unit_bs if b.execution_error is None)
        unit_success_rate = (unit_success / total_branches * 100) if total_branches > 0 else 0
        unit_costs = [b.estimated_cost for b in unit_bs if b.estimated_cost > 0]
        max_cost = max(unit_costs) if unit_costs else 0.0
        avg_cost = (sum(unit_costs) / len(unit_costs)) if unit_costs else 0.0
        unit_summaries.append((unit_id, total_branches, f"{unit_success_rate:.0f}%", max_cost, avg_cost))

    unit_summaries.sort(key=lambda x: x[3], reverse=True)
    for unit_id, total_branches, success_rate, max_cost, avg_cost in unit_summaries:
        lines.append(f"| `{unit_id}` | {total_branches} | {success_rate} | {max_cost:.2f} | {avg_cost:.2f} |")
    lines.append("")

    # --- Actual time distribution (if available) ---
    timed_bs = [b for b in baselines if b.actual_time_ms is not None]
    if timed_bs:
        times = [b.actual_time_ms for b in timed_bs]
        lines.append("## 实际执行时间分布")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 有耗时分支 | {len(timed_bs)} |")
        lines.append(f"| 最快 | {min(times):.2f} ms |")
        lines.append(f"| 最慢 | {max(times):.2f} ms |")
        lines.append(f"| 平均 | {sum(times) / len(times):.2f} ms |")
        lines.append("")

    # --- Execution errors ---
    error_bs = [b for b in baselines if b.execution_error is not None]
    if error_bs:
        lines.append(f"## 执行错误（共 {len(error_bs)} 条）")
        lines.append("")
        lines.extend(f"- **`{b.sql_unit_id}`.`{b.path_id}`**: `{b.execution_error}`" for b in error_bs[:10])
        if len(error_bs) > 10:
            lines.append(f"- ... 还有 {len(error_bs) - 10} 条错误")
        lines.append("")

    # --- Statistics ---
    lines.append("## 统计信息")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| SQL Unit 数 | {len(units_map)} |")
    lines.append(f"| 分支总数 | {total} |")
    lines.append(f"| 输出文件数 | {files_count} |")
    lines.append(f"| 输出大小 | {file_size_bytes:,} 字节 |")
    lines.append("")

    lines.append("---")
    lines.append("*由 SQL Optimizer 生成 - RECOGNITION 阶段*")

    result = "\n".join(lines)

    max_output_size = 50 * 1024
    if len(result) > max_output_size:
        result = result[:max_output_size] + "\n\n... (output truncated to 50KB)"

    return result
