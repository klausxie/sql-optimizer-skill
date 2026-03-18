"""
V8 Rule Engine for SQL Optimization

Self-contained rule engine that applies built-in optimization rules to SQL.
Zero coupling with legacy code - no imports from sqlopt.stages.optimize or sqlopt.llm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RuleResult:
    """Result of applying an optimization rule."""

    rule_name: str
    original_sql: str
    optimized_sql: str
    improvement: str


class Rule:
    """Base class for optimization rules."""

    def __init__(self, name: str):
        self.name = name

    def apply(self, sql: str) -> RuleResult | None:
        """Apply the rule to SQL. Returns RuleResult if optimization applies, None otherwise."""
        raise NotImplementedError

    def _is_subquery_in_select(self, sql: str) -> bool:
        """Check if SQL contains a correlated subquery in SELECT clause."""
        # Pattern to detect SELECT with subquery (correlated subquery pattern)
        # Matches: SELECT (SELECT ... FROM ... WHERE ...) FROM ...
        pattern = r"SELECT\s*\([^)]*SELECT[^)]*\)"
        return bool(re.search(pattern, sql, re.IGNORECASE | re.DOTALL))


class AvoidSelectStarRule(Rule):
    """Replace SELECT * with explicit column list where possible."""

    def __init__(self):
        super().__init__("avoid_select_star")

    def apply(self, sql: str) -> RuleResult | None:
        pattern = r"\bSELECT\s+\*\s+FROM\b"
        if re.search(pattern, sql, re.IGNORECASE):
            # For now, we can only suggest explicit columns if we know the schema
            # In a real implementation, this would need table metadata
            original_sql = sql
            optimized_sql = sql  # Placeholder - would need column metadata
            improvement = "SELECT * prevents index-only scans and fetches unnecessary columns. Specify explicit columns for better performance."

            # If we can't determine columns, at least flag it
            return RuleResult(
                rule_name=self.name,
                original_sql=original_sql,
                optimized_sql=optimized_sql,
                improvement=improvement,
            )
        return None


class AddLimitRule(Rule):
    """Add LIMIT 1000 to prevent unbounded queries."""

    def __init__(self):
        super().__init__("add_limit")

    def apply(self, sql: str) -> RuleResult | None:
        sql_upper = sql.upper().strip()

        # Skip if already has LIMIT
        if "LIMIT" in sql_upper:
            return None

        # Skip if it's a DDL statement
        ddl_patterns = [
            "CREATE ",
            "DROP ",
            "ALTER ",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "TRUNCATE ",
        ]
        if any(sql_upper.startswith(p.strip()) for p in ddl_patterns):
            return None

        original_sql = sql
        optimized_sql = sql.rstrip(";") + " LIMIT 1000"
        improvement = "Without LIMIT, queries can return unbounded results causing memory pressure and slow response times. LIMIT 1000 is a safe default."

        return RuleResult(
            rule_name=self.name,
            original_sql=original_sql,
            optimized_sql=optimized_sql,
            improvement=improvement,
        )


class AvoidSubqueryInSelectRule(Rule):
    """Suggest JOIN instead of correlated subquery in SELECT clause."""

    def __init__(self):
        super().__init__("avoid_subquery_in_select")

    def apply(self, sql: str) -> RuleResult | None:
        # Pattern: SELECT (SELECT ... FROM outer_table WHERE outer.col = inner.col ...) FROM ...
        pattern = (
            r"SELECT\s*\(\s*SELECT\s+.+?\s+FROM\s+\w+(?:\s+\w+)?\s+WHERE\s+.+?\)\s+FROM"
        )

        if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
            original_sql = sql
            # Extract the subquery for the suggestion
            match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
            if match:
                subquery = match.group(0)
                # Suggest rewriting as a JOIN
                improvement = f"Correlated subquery in SELECT clause detected. Consider rewriting as a JOIN for better performance. Example pattern: SELECT (subquery) FROM main_table JOIN sub_table ON condition"
            else:
                improvement = "Correlated subquery in SELECT clause detected. Rewrite as JOIN for better performance."

            return RuleResult(
                rule_name=self.name,
                original_sql=original_sql,
                optimized_sql=original_sql,  # We can't auto-rewrite without schema
                improvement=improvement,
            )
        return None


class RuleEngine:
    """
    V8 Rule Engine for SQL Optimization.

    Applies built-in optimization rules to SQL statements.
    """

    def __init__(self):
        self.rules: list[Rule] = [
            AvoidSelectStarRule(),
            AddLimitRule(),
            AvoidSubqueryInSelectRule(),
        ]

    def apply_all(self, sql: str) -> list[RuleResult]:
        """Apply all rules to the SQL and return list of results."""
        results = []
        for rule in self.rules:
            result = rule.apply(sql)
            if result:
                results.append(result)
        return results

    def add_rule(self, rule: Rule) -> None:
        """Add a custom rule to the engine."""
        self.rules.append(rule)


def apply_rules(sql: str) -> list[RuleResult]:
    """
    Apply all optimization rules to the given SQL.

    Args:
        sql: SQL statement to optimize

    Returns:
        List of RuleResult for each applicable optimization
    """
    engine = RuleEngine()
    return engine.apply_all(sql)


if __name__ == "__main__":
    # Example usage
    result = apply_rules("SELECT * FROM users WHERE id = 1")
    for r in result:
        print(f"Rule: {r.rule_name}")
        print(f"Original: {r.original_sql}")
        print(f"Optimized: {r.optimized_sql}")
        print(f"Improvement: {r.improvement}")
        print("---")
