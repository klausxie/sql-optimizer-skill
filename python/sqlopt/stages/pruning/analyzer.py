"""
Pruning Stage - Risk Detection and Analysis Module

Detects performance risks in SQL statements.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskIssue:
    """Represents a detected risk issue in SQL."""

    sql_key: str
    risk_type: str
    severity: str  # HIGH, MEDIUM, LOW
    location: Optional[dict] = None  # {line, column}
    suggestion: str = ""

    def to_dict(self) -> dict:
        result = {
            "sqlKey": self.sql_key,
            "risk_type": self.risk_type,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }
        if self.location:
            result["location"] = self.location
        return result


class RiskDetector:
    """Detects performance risks in SQL statements."""

    # Pattern definitions
    # Note: (?i) must be at the start of the ENTIRE pattern, not in each alternative
    PREFIX_WILDCARD_PATTERN = re.compile(
        r"(?i)(?:LIKE|ILIKE)\s*['\"]%\s*\+?\s*(\w+)|(\w+)\s+LIKE\s+['\"]%"
    )
    SUFFIX_WILDCARD_PATTERN = re.compile(
        r"(?i)(\w+)\s+LIKE\s+['\"][^'\"]*%[^'\"]*['\"]"
    )
    FUNCTION_WRAP_PATTERN = re.compile(
        r"(?i)\b(UPPER|LOWER|TRIM|LTRIM|RTRIM|"
        r"SUBSTRING|SUBSTR|LEFT|RIGHT|CHAR_LENGTH|LENGTH)\s*\(\s*(\w+)\s*\)"
    )
    SELECT_STAR_PATTERN = re.compile(r"(?i)\bSELECT\s+\*\s+FROM\b")
    MISSING_INDEX_PATTERN = re.compile(r"(?i)\bWHERE\s+\w+\s*[=<>]")
    N_PLUS_1_PATTERN = re.compile(
        r"(?i)(?:IN\s*\(\s*SELECT|EXISTS\s*\(\s*SELECT|"
        r"JOIN\s+\w+\s+ON\s+\w+\.\w+\s*=\s*\w+\.\w+.*WHERE)"
    )

    def __init__(self):
        self.issues: list[RiskIssue] = []

    def detect_prefix_wildcard(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect prefix wildcard patterns like '%value%'."""
        issues = []
        matches = self.PREFIX_WILDCARD_PATTERN.finditer(sql)
        for match in matches:
            column = match.group(1) or match.group(2)
            issues.append(
                RiskIssue(
                    sql_key=sql_key,
                    risk_type="prefix_wildcard",
                    severity="HIGH",
                    location={"line": 1, "column": match.start()},
                    suggestion=f"Use full-text index or reverse the LIKE pattern to suffix-only (column%)",
                )
            )
        return issues

    def detect_suffix_wildcard(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect suffix wildcard patterns like 'value%'."""
        issues = []
        matches = self.SUFFIX_WILDCARD_PATTERN.finditer(sql)
        for match in matches:
            issues.append(
                RiskIssue(
                    sql_key=sql_key,
                    risk_type="suffix_wildcard",
                    severity="LOW",
                    location={"line": 1, "column": match.start()},
                    suggestion=f"Suffix wildcard is acceptable if column has index. Consider covering index.",
                )
            )
        return issues

    def detect_function_wrap(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect function-wrapped columns in WHERE clause."""
        issues = []
        matches = self.FUNCTION_WRAP_PATTERN.finditer(sql)
        for match in matches:
            func_name = match.group(1).upper()
            column = match.group(2)
            issues.append(
                RiskIssue(
                    sql_key=sql_key,
                    risk_type="function_wrap",
                    severity="MEDIUM",
                    location={"line": 1, "column": match.start()},
                    suggestion=f"Function {func_name}({column}) prevents index usage. Consider using expression index or reversing the logic.",
                )
            )
        return issues

    def detect_select_star(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect SELECT * pattern."""
        issues = []
        if self.SELECT_STAR_PATTERN.search(sql):
            issues.append(
                RiskIssue(
                    sql_key=sql_key,
                    risk_type="select_star",
                    severity="LOW",
                    location={"line": 1, "column": 0},
                    suggestion="Avoid SELECT *. Specify only needed columns to reduce data transfer and prevent issues with schema changes.",
                )
            )
        return issues

    def detect_missing_index(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect WHERE clause without index hint."""
        issues = []
        if self.MISSING_INDEX_PATTERN.search(sql):
            # Check if there's already an index hint
            has_index_hint = bool(re.search(r"(?i)\bUSE\s+INDEX\b|FORCE\s+INDEX", sql))
            if not has_index_hint:
                issues.append(
                    RiskIssue(
                        sql_key=sql_key,
                        risk_type="missing_index",
                        severity="MEDIUM",
                        location={"line": 1, "column": 0},
                        suggestion="Consider adding index hint or creating index on filtered columns.",
                    )
                )
        return issues

    def detect_n_plus_1(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Detect potential N+1 query pattern."""
        issues = []
        if self.N_PLUS_1_PATTERN.search(sql):
            issues.append(
                RiskIssue(
                    sql_key=sql_key,
                    risk_type="n_plus_1",
                    severity="HIGH",
                    location={"line": 1, "column": 0},
                    suggestion="Potential N+1 pattern detected. Consider using JOIN or batch query instead of subquery in IN clause.",
                )
            )
        return issues

    def analyze(self, sql: str, sql_key: str) -> list[RiskIssue]:
        """Run all risk detectors on a single SQL statement."""
        issues = []
        issues.extend(self.detect_prefix_wildcard(sql, sql_key))
        issues.extend(self.detect_suffix_wildcard(sql, sql_key))
        issues.extend(self.detect_function_wrap(sql, sql_key))
        issues.extend(self.detect_select_star(sql, sql_key))
        issues.extend(self.detect_missing_index(sql, sql_key))
        issues.extend(self.detect_n_plus_1(sql, sql_key))
        return issues


def analyze_risks(sql_units: list[dict]) -> list[dict]:
    """
    Analyze SQL units for performance risks.

    Args:
        sql_units: List of SQL unit dicts with at least 'sqlKey' and 'sql' fields

    Returns:
        List of risk issues as dicts
    """
    detector = RiskDetector()
    all_issues = []

    for unit in sql_units:
        sql_key = unit.get("sqlKey") or unit.get("sql_key")
        sql_content = unit.get("sql") or unit.get("content") or ""

        if not sql_key:
            continue

        issues = detector.analyze(sql_content, sql_key)
        all_issues.extend(issues)

    return [issue.to_dict() for issue in all_issues]
