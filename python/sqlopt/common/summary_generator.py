"""Summary generator for stage execution reports.

This module provides utilities for generating human-readable SUMMARY.md content
from stage execution data. It does NOT perform file I/O - it only generates text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


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
