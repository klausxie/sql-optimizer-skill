"""Analyze SQL issues and determine complexity.

This stage handles:
- Analyze SQL problems
- Determine complexity (simple/complex)
- Decide optimization method (rules/llm)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Issue:
    """SQL issue found during analysis."""
    type: str           # FULL_SCAN, NO_LIMIT, etc.
    severity: str       # HIGH, MEDIUM, LOW
    description: str
    location: str | None = None


@dataclass
class AnalysisResult:
    """Analysis result for a SQL."""
    sql_key: str
    issues: list[Issue]
    complexity: str      # "simple" or "complex"
    optimization_method: str  # "rules" or "llm"
    reasoning: str


def analyze_sql(
    sql: str,
    sql_key: str,
    execute_result: dict[str, Any] | None = None
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
        issues.append(Issue(
            type="SELECT_STAR",
            severity="HIGH",
            description="SELECT * returns all columns, consider specifying columns"
        ))
    
    # Check for missing WHERE
    if re.search(r'\bWHERE\b', sql_upper) is None and "SELECT" in sql_upper:
        issues.append(Issue(
            type="NO_WHERE",
            severity="HIGH",
            description="No WHERE clause - potential full table scan"
        ))
    
    # Check for missing LIMIT
    if "SELECT" in sql_upper and re.search(r'\bLIMIT\b', sql_upper) is None:
        issues.append(Issue(
            type="NO_LIMIT",
            severity="MEDIUM",
            description="No LIMIT clause - may return large result set"
        ))
    
    # Check for LIKE with leading wildcard
    if re.search(r"LIKE\s+['\"]%", sql, re.IGNORECASE):
        issues.append(Issue(
            type="LEADING_WILDCARD",
            severity="HIGH",
            description="LIKE with leading wildcard cannot use index"
        ))
    
    # Check for ORDER BY RAND()
    if re.search(r"ORDER\s+BY\s+RAND\(\)", sql_upper):
        issues.append(Issue(
            type="ORDER_BY_RAND",
            severity="HIGH",
            description="ORDER BY RAND() is very slow"
        ))
    
    # Check execution result if available
    if execute_result:
        plan = execute_result.get("plan", "")
        
        # Check for full table scan
        if "Full Table Scan" in plan or "Seq Scan" in plan:
            issues.append(Issue(
                type="FULL_SCAN",
                severity="HIGH",
                description="Execution plan shows full table scan"
            ))
        
        # Check for high duration
        duration_ms = execute_result.get("duration_ms", 0)
        if duration_ms > 1000:
            issues.append(Issue(
                type="SLOW_QUERY",
                severity="HIGH",
                description=f"Execution time: {duration_ms}ms (> 1000ms)"
            ))
        
        # Check for large row count
        rows = execute_result.get("rows", 0)
        if rows > 10000:
            issues.append(Issue(
                type="LARGE_RESULT",
                severity="MEDIUM",
                description=f"Returns {rows} rows (> 10000)"
            ))
    
    # Determine complexity based on issues
    high_issues = [i for i in issues if i.severity == "HIGH"]
    complex_patterns = [
        r'\bJOIN\b',           # JOIN
        r'\bSUBQUERY\b',        # Subquery
        r'\bUNION\b',          # UNION
        r'\bHAVING\b',          # HAVING
        r'\bGROUP\s+BY\b',     # GROUP BY with aggregation
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
        reasoning=reasoning
    )
