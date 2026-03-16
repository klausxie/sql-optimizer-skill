"""Analyze SQL issues and determine complexity.

This stage handles:
- Diagnose branches (EXPLAIN analysis)
- Analyze SQL problems
- Determine complexity (simple/complex)
- Decide optimization method (rules/llm)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..errors import StageError
from ..io_utils import read_jsonl, write_jsonl
from ..manifest import log_event


@dataclass
class Issue:
    """SQL issue found during analysis."""

    type: str  # FULL_SCAN, NO_LIMIT, etc.
    severity: str  # HIGH, MEDIUM, LOW
    description: str
    location: str | None = None


@dataclass
class AnalysisResult:
    """Analysis result for a SQL."""

    sql_key: str
    issues: list[Issue]
    complexity: str  # "simple" or "complex"
    optimization_method: str  # "rules" or "llm"
    reasoning: str


def analyze_sql(
    sql: str, sql_key: str, execute_result: dict[str, Any] | None = None
) -> AnalysisResult:
    """Analyze a SQL and determine issues and complexity.

    Args:
        sql: The SQL to analyze
        sql_key: Unique identifier for this SQL
        execute_result: Optional execution result (from EXPLAIN)

    Returns:
        AnalysisResult with issues, complexity, and method
    """
    issues: list[Issue] = []
    sql_upper = sql.upper()

    # Check for SELECT *
    if "SELECT *" in sql_upper:
        issues.append(
            Issue(
                type="SELECT_STAR",
                severity="HIGH",
                description="SELECT * returns all columns, consider specifying columns",
            )
        )

    # Check for missing WHERE
    if re.search(r"\bWHERE\b", sql_upper) is None and "SELECT" in sql_upper:
        issues.append(
            Issue(
                type="NO_WHERE",
                severity="HIGH",
                description="No WHERE clause - potential full table scan",
            )
        )

    # Check for missing LIMIT
    if "SELECT" in sql_upper and re.search(r"\bLIMIT\b", sql_upper) is None:
        issues.append(
            Issue(
                type="NO_LIMIT",
                severity="MEDIUM",
                description="No LIMIT clause - may return large result set",
            )
        )

    # Check for LIKE with leading wildcard
    if re.search(r"LIKE\s+['\"]%", sql, re.IGNORECASE):
        issues.append(
            Issue(
                type="LEADING_WILDCARD",
                severity="HIGH",
                description="LIKE with leading wildcard cannot use index",
            )
        )

    # Check for ORDER BY RAND()
    if re.search(r"ORDER\s+BY\s+RAND\(\)", sql_upper):
        issues.append(
            Issue(
                type="ORDER_BY_RAND",
                severity="HIGH",
                description="ORDER BY RAND() is very slow",
            )
        )

    # Check execution result if available
    if execute_result:
        plan = execute_result.get("plan", "")

        # Check for full table scan
        if "Full Table Scan" in plan or "Seq Scan" in plan:
            issues.append(
                Issue(
                    type="FULL_SCAN",
                    severity="HIGH",
                    description="Execution plan shows full table scan",
                )
            )

        # Check for high duration
        duration_ms = execute_result.get("duration_ms", 0)
        if duration_ms > 1000:
            issues.append(
                Issue(
                    type="SLOW_QUERY",
                    severity="HIGH",
                    description=f"Execution time: {duration_ms}ms (> 1000ms)",
                )
            )

        # Check for large row count
        rows = execute_result.get("rows", 0)
        if rows > 10000:
            issues.append(
                Issue(
                    type="LARGE_RESULT",
                    severity="MEDIUM",
                    description=f"Returns {rows} rows (> 10000)",
                )
            )

    # Determine complexity based on issues
    high_issues = [i for i in issues if i.severity == "HIGH"]
    complex_patterns = [
        r"\bJOIN\b",  # JOIN
        r"\bSUBQUERY\b",  # Subquery
        r"\bUNION\b",  # UNION
        r"\bHAVING\b",  # HAVING
        r"\bGROUP\s+BY\b",  # GROUP BY with aggregation
    ]

    is_complex = len(high_issues) > 2 or any(
        re.search(p, sql_upper) for p in complex_patterns
    )

    complexity = "complex" if is_complex else "simple"

    # Determine optimization method
    if complexity == "simple":
        optimization_method = "rules"
        reasoning = "Simple SQL - use rule-based optimization"
    else:
        optimization_method = "llm"
        reasoning = "Complex SQL - use LLM for better optimization"

    return AnalysisResult(
        sql_key=sql_key,
        issues=issues,
        complexity=complexity,
        optimization_method=optimization_method,
        reasoning=reasoning,
    )


def execute(
    config: dict[str, Any], run_dir: Path, validator: ContractValidator
) -> list[dict[str, Any]]:
    """Execute analyze stage: diagnose branches and identify problems.

    This stage:
    1. Loads SQL units from scan stage
    2. Diagnoses each branch (EXPLAIN analysis)
    3. Identifies problematic branches
    4. Determines optimization method

    Args:
        config: Configuration dict
        run_dir: Run directory path
        validator: Contract validator

    Returns:
        List of analyzed SQL units with diagnosis results
    """
    manifest_path = run_dir / "manifest.jsonl"
    sqlunits_path = run_dir / "scan.sqlunits.jsonl"

    if not sqlunits_path.exists():
        raise StageError(
            "scan.sqlunits.jsonl not found - run scan stage first",
            reason_code="ANALYZE_NO_SCAN_DATA",
        )

    units = list(read_jsonl(sqlunits_path))
    if not units:
        raise StageError("no sql units to analyze", reason_code="ANALYZE_NO_UNITS")

    # Import diagnose_branches (lazy to avoid circular imports)
    from ..adapters.branch_diagnose import diagnose_branches

    # Diagnose branches for each unit
    branch_cfg = config.get("branch", {})
    diagnose_enabled = branch_cfg.get("diagnose", True)

    for unit in units:
        branches = unit.get("branches", [])
        if not branches:
            continue

        # Diagnose branches (EXPLAIN analysis)
        if diagnose_enabled:
            branches = diagnose_branches(branches, config)
            unit["branches"] = branches

        # Count problematic branches
        problem_branches = [
            b for b in branches if b.get("baseline", {}).get("problematic", False)
        ]
        unit["problemBranchCount"] = len(problem_branches)

        # Determine if this SQL needs optimization
        unit["needsOptimization"] = len(problem_branches) > 0

        # Analyze SQL complexity for optimization method
        sql = unit.get("sql", "")
        analysis = analyze_sql(sql, unit.get("sqlKey", ""))
        unit["analysis"] = {
            "issues": [
                {"type": i.type, "severity": i.severity, "description": i.description}
                for i in analysis.issues
            ],
            "complexity": analysis.complexity,
            "optimizationMethod": analysis.optimization_method,
            "reasoning": analysis.reasoning,
        }

    # Write analyzed units
    analyzed_path = run_dir / "analyzed.sqlunits.jsonl"
    write_jsonl(analyzed_path, units)

    # Log completion
    total_units = len(units)
    units_with_problems = sum(1 for u in units if u.get("needsOptimization", False))
    log_event(
        manifest_path,
        "analyze",
        "done",
        {
            "totalUnits": total_units,
            "unitsWithProblems": units_with_problems,
            "diagnoseEnabled": diagnose_enabled,
        },
    )

    return units
