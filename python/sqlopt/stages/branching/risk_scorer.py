from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlopt.stages.branching.branch_strategy import LadderSamplingStrategy
from sqlopt.stages.branching.dimension_extractor import BranchDimension

if TYPE_CHECKING:
    from sqlopt.contracts.init import FieldDistribution

    __all__ = ["SQLDeltaRiskScorer"]


@dataclass
class SQLDeltaRiskScorer:
    """Score branch dimensions using their SQL fragment delta."""

    table_metadata: dict[str, dict] | None = None
    field_distributions: dict[str, list["FieldDistribution"]] | None = None

    def __post_init__(self) -> None:
        self._strategy = LadderSamplingStrategy(
            table_metadata=self.table_metadata or {},
            field_distributions=self.field_distributions,
        )

    def set_field_distributions(self, field_distributions: dict[str, list["FieldDistribution"]] | None) -> None:
        """Set field distributions for risk scoring."""
        self.field_distributions = field_distributions
        self._strategy.field_distributions = field_distributions or {}

    def score_dimension(self, dimension: BranchDimension) -> float:
        score, _reasons = self.score_sql(dimension.sql_fragment or dimension.condition)
        score += dimension.depth * 0.25
        return score

    def score_sql(self, sql: str) -> tuple[float, list[str]]:
        text = sql.strip()
        score = self._strategy._get_condition_weight(text) if text else 0.0  # noqa: SLF001
        # Add weight adjustments from field distributions
        score += self._compute_field_distribution_weights(text)
        reasons = self._collect_reasons(text)
        return score, reasons

    def score_branch(
        self,
        sql: str,
        active_conditions: list[str],
        risk_flags: list[str],
    ) -> tuple[float, list[str]]:
        score, reasons = self.score_sql(sql)
        if active_conditions:
            reasons.extend(f"active:{condition}" for condition in active_conditions)
        if risk_flags:
            reasons.extend(f"flag:{flag}" for flag in risk_flags)
        return score, self._dedupe(reasons)

    def _collect_reasons(self, sql: str) -> list[str]:
        text = sql.strip()
        if not text:
            return []

        reasons: list[str] = []
        sql_lower = text.lower()

        if " join " in sql_lower:
            reasons.append("join")
        if re.search(r"select\s+\*", sql_lower):
            reasons.append("select_star")
        if "order by" in sql_lower:
            reasons.append("order_by")
        if "group by" in sql_lower:
            reasons.append("group_by")
        if " having " in f" {sql_lower} ":
            reasons.append("having")
        if re.search(r"like\s+(concat\(|['\"]%)", sql_lower):
            reasons.append("like_prefix")
        if re.search(r"\b(?:not\s+)?in\s*\(", sql_lower):
            reasons.append("in_clause")
        if "not in" in sql_lower:
            reasons.append("not_in")
        if "exists" in sql_lower:
            reasons.append("exists")
        if re.search(r"\b(offset|limit)\b", sql_lower):
            reasons.append("pagination")
        if "distinct" in sql_lower:
            reasons.append("distinct")
        if re.search(r"\bunion\b", sql_lower):
            reasons.append("union")
        if re.search(r"\(\s*select\b", sql_lower):
            reasons.append("subquery")
        for func_pattern in self._strategy.FUNCTION_WRAPPER_PATTERNS:
            if func_pattern in sql_lower:
                reasons.append(f"function:{func_pattern[:-1]}")
                break

        metadata_reasons = self._collect_metadata_reasons(sql_lower)
        reasons.extend(metadata_reasons)
        fd_reasons = self._collect_field_distribution_reasons(sql_lower)
        reasons.extend(fd_reasons)
        return self._dedupe(reasons)

    def _collect_metadata_reasons(self, sql_lower: str) -> list[str]:
        if not self.table_metadata:
            return []

        reasons: list[str] = []
        for table_name, metadata in self.table_metadata.items():
            if table_name not in sql_lower:
                continue
            size = metadata.get("size")
            if size == "large":
                reasons.append(f"table:{table_name}:large")
            elif size == "medium":
                reasons.append(f"table:{table_name}:medium")
        return reasons

    def _compute_field_distribution_weights(self, sql: str) -> float:
        if not self.field_distributions:
            return 0.0
        sql_lower = sql.strip().lower()
        weight_adjustment = 0.0
        for table_name, distributions in self.field_distributions.items():
            if table_name not in sql_lower:
                continue
            for dist in distributions:
                col_name = dist.column_name.lower()
                if col_name not in sql_lower:
                    continue
                total_rows = self._get_total_rows(dist)
                null_ratio = dist.null_count / max(total_rows, 1)
                if null_ratio > 0.1:
                    weight_adjustment += 2.0
                if dist.distinct_count < 10:
                    weight_adjustment += 1.0
                if dist.top_values and len(dist.top_values) > 0:
                    top_value_count = dist.top_values[0].get("count", 0)
                    non_null_rows = max(total_rows - dist.null_count, 1)
                    if non_null_rows > 0 and top_value_count / non_null_rows > 0.8:
                        weight_adjustment += 2.0
        return weight_adjustment

    def _collect_field_distribution_reasons(self, sql_lower: str) -> list[str]:
        if not self.field_distributions:
            return []

        reasons: list[str] = []
        for table_name, distributions in self.field_distributions.items():
            if table_name not in sql_lower:
                continue
            for dist in distributions:
                col_name = dist.column_name.lower()
                if col_name not in sql_lower:
                    continue
                total_rows = self._get_total_rows(dist)
                null_ratio = dist.null_count / max(total_rows, 1)
                if null_ratio > 0.1:
                    reasons.append(f"field_null_high:{col_name}")
                if dist.distinct_count < 10:
                    reasons.append(f"field_low_card:{col_name}")
                if dist.top_values and len(dist.top_values) > 0:
                    top_value_count = dist.top_values[0].get("count", 0)
                    non_null_rows = max(total_rows - dist.null_count, 1)
                    if non_null_rows > 0 and top_value_count / non_null_rows > 0.8:
                        reasons.append(f"field_skewed:{col_name}")
        return reasons

    @staticmethod
    def _get_total_rows(dist: "FieldDistribution") -> int:
        if getattr(dist, "total_count", 0):
            return dist.total_count
        return dist.distinct_count + dist.null_count

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value and value not in seen:
                seen.add(value)
                ordered.append(value)
        return ordered
