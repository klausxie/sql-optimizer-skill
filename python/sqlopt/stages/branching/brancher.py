"""
Branching Stage - Branch Generation

Generates executable SQL branches from MyBatis dynamic SQL.
"""

from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class Branch:
    """SQL 分支"""

    branch_id: str
    active_conditions: list[str]
    sql: str
    condition_count: int
    risk_flags: list[str] = field(default_factory=list)


class Brancher:
    """分支生成器"""

    # Risk patterns
    RISK_PATTERNS = {
        "prefix_wildcard": (r"['\"]%['\"]?\s*\+", "Leading wildcard"),
        "suffix_wildcard": (r"\+\s*['\"]%['\"]?", "Trailing wildcard"),
        "function_wrap": (r"\b(UPPER|LOWER|TRIM)\s*\(", "Function on column"),
    }

    def __init__(self, strategy: str = "all_combinations", max_branches: int = 100):
        self.strategy = strategy
        self.max_branches = max_branches

    def generate(self, sql: str, conditions: list[dict] = None) -> list[Branch]:
        """生成所有可能的 SQL 分支"""
        if not conditions:
            # No dynamic conditions, return single branch
            return [
                Branch(
                    branch_id="default",
                    active_conditions=[],
                    sql=sql,
                    condition_count=0,
                    risk_flags=self._detect_risks(sql),
                )
            ]

        # Generate combinations based on strategy
        if self.strategy == "all_combinations":
            return self._generate_all_combinations(sql, conditions)
        elif self.strategy == "pairwise":
            return self._generate_pairwise(sql, conditions)
        else:
            return self._generate_all_combinations(sql, conditions)

    def _generate_all_combinations(
        self, sql: str, conditions: list[dict]
    ) -> list[Branch]:
        """生成所有条件组合"""
        branches = []

        # Simple case: treat each condition as boolean toggle
        for i, combo in enumerate(self._bool_combinations(len(conditions))):
            active = [conditions[j]["condition"] for j, val in enumerate(combo) if val]

            branch_sql = self._apply_conditions(sql, active)

            branches.append(
                Branch(
                    branch_id=f"branch_{i}",
                    active_conditions=active,
                    sql=branch_sql,
                    condition_count=len(active),
                    risk_flags=self._detect_risks(branch_sql),
                )
            )

            if len(branches) >= self.max_branches:
                break

        return branches

    def _generate_pairwise(self, sql: str, conditions: list[dict]) -> list[Branch]:
        """生成配对测试组合"""
        # Simplified pairwise - just return a few combinations
        branches = []

        # Default branch
        branches.append(
            Branch(
                branch_id="default",
                active_conditions=[],
                sql=sql,
                condition_count=0,
                risk_flags=self._detect_risks(sql),
            )
        )

        # Each condition individually
        for i, cond in enumerate(conditions):
            branch_sql = self._apply_conditions(sql, [cond["condition"]])
            branches.append(
                Branch(
                    branch_id=f"branch_{i}",
                    active_conditions=[cond["condition"]],
                    sql=branch_sql,
                    condition_count=1,
                    risk_flags=self._detect_risks(branch_sql),
                )
            )

        return branches

    def _bool_combinations(self, n: int):
        """生成 n 位布尔组合"""
        for i in range(2**n):
            yield tuple(bool(i & (1 << j)) for j in range(n))

    def _apply_conditions(self, sql: str, active_conditions: list[str]) -> str:
        """应用条件到 SQL"""
        # Simplified: just return SQL as-is
        # Real implementation would parse and render
        return sql

    def _detect_risks(self, sql: str) -> list[str]:
        """检测 SQL 风险"""
        risks = []

        for pattern_name, (pattern, _) in self.RISK_PATTERNS.items():
            if re.search(pattern, sql, re.IGNORECASE):
                risks.append(pattern_name)

        return risks


# Convenience function
def generate_branches(
    sql: str, conditions: list[dict] = None, strategy: str = "all_combinations"
) -> list[dict]:
    """生成 SQL 分支"""
    brancher = Brancher(strategy=strategy)
    branches = brancher.generate(sql, conditions)

    return [
        {
            "branch_id": b.branch_id,
            "active_conditions": b.active_conditions,
            "sql": b.sql,
            "condition_count": b.condition_count,
            "risk_flags": b.risk_flags,
        }
        for b in branches
    ]
