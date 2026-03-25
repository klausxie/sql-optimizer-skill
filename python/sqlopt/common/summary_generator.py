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
## Data Contracts

This section describes the core data structures used throughout the SQL Optimizer pipeline.

### SQLUnit

A **SQLUnit** represents a single SQL statement extracted from a MyBatis XML mapper file.

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique identifier for the SQL unit |
| mapper_file | str | Path to the source XML mapper file |
| sql_id | str | The `id` attribute from the XML statement tag |
| sql_text | str | Raw SQL text with MyBatis tags preserved |
| statement_type | str | Type: SELECT, INSERT, UPDATE, DELETE |

### SQLBranch

A **SQLBranch** represents an expanded version of a SQL unit with dynamic MyBatis tags resolved.

| Field | Type | Description |
|-------|------|-------------|
| path_id | str | Unique identifier for this branch |
| condition | str | Optional condition that activates this branch |
| expanded_sql | str | SQL with dynamic tags fully expanded |
| is_valid | bool | Whether the expanded SQL is syntactically valid |
| risk_flags | list[str] | Potential issues detected in the SQL |
| active_conditions | list[str] | Conditions that must be true for this branch |
| risk_score | float | Computed risk score (0.0 = safe, 1.0 = risky) |
| score_reasons | list[str] | Explanations for the risk score |

### PerformanceBaseline

A **PerformanceBaseline** captures the SQL execution plan and estimated cost from the database.

| Field | Type | Description |
|-------|------|-------------|
| sql_unit_id | str | Reference to the source SQLUnit |
| path_id | str | Reference to the specific SQLBranch |
| plan | dict | Database execution plan (EXPLAIN output) |
| estimated_cost | float | Estimated execution cost from the planner |
| actual_time_ms | float | Actual execution time in milliseconds (if available) |

### OptimizationProposal

An **OptimizationProposal** represents an LLM-generated suggestion for improving SQL performance.

| Field | Type | Description |
|-------|------|-------------|
| sql_unit_id | str | Reference to the source SQLUnit |
| path_id | str | Reference to the specific SQLBranch |
| original_sql | str | The original SQL before optimization |
| optimized_sql | str | The suggested optimized SQL |
| rationale | str | Explanation of why this optimization helps |
| confidence | float | LLM confidence score (0.0 to 1.0) |
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

    lines.append(f"# {summary.stage_name.upper()} Stage Summary")
    lines.append("")
    lines.append(f"**Run ID:** {summary.run_id}")
    lines.append(f"**Duration:** {summary.duration_seconds:.2f} seconds")
    lines.append("")

    lines.append("## Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| SQL Units | {summary.sql_units_count} |")
    lines.append(f"| Branches | {summary.branches_count} |")
    lines.append(f"| Files | {summary.files_count} |")
    lines.append(f"| File Size | {summary.file_size_bytes:,} bytes |")
    lines.append("")

    lines.append(_DATA_CONTRACT_GUIDE)

    if summary.errors:
        lines.append("## Errors")
        lines.append("")
        for i, error in enumerate(summary.errors, 1):
            lines.append(f"{i}. {truncate_text(error, max_chars=500)}")
        lines.append("")

    if summary.warnings:
        lines.append("## Warnings")
        lines.append("")
        for i, warning in enumerate(summary.warnings, 1):
            lines.append(f"{i}. {truncate_text(warning, max_chars=500)}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by SQL Optimizer - Stage: {summary.stage_name}*")

    result = "\n".join(lines)

    max_output_size = 50 * 1024
    if len(result) > max_output_size:
        result = result[:max_output_size] + "\n\n... (output truncated to 50KB)"

    return result
