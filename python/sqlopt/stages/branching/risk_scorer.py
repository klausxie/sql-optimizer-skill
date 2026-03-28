"""Risk scoring for branch dimensions and rendered SQL.

This module delegates all risk detection to RiskRuleRegistry.
The public API (score_dimension, score_sql, score_branch) is unchanged
so existing callers see no difference in behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlopt.common.rules import RiskRuleRegistry
from sqlopt.stages.branching.dimension_extractor import BranchDimension

if TYPE_CHECKING:
    from sqlopt.contracts.init import FieldDistribution

    __all__ = ["SQLDeltaRiskScorer"]


@dataclass
class SQLDeltaRiskScorer:
    """Score branch dimensions and rendered SQL using RiskRuleRegistry.

    Public API is unchanged from before; internally all detection is
    delegated to RiskRuleRegistry.evaluate_phase1 / evaluate_phase2.
    """

    table_metadata: dict[str, dict] | None = None
    field_distributions: dict[str, list["FieldDistribution"]] | None = None

    def __post_init__(self) -> None:
        self._registry = RiskRuleRegistry.global_instance()

    def set_field_distributions(self, field_distributions: dict[str, list["FieldDistribution"]] | None) -> None:
        self.field_distributions = field_distributions

    def score_dimension(self, dimension: BranchDimension) -> float:
        score, _ = self._registry.evaluate_phase1(dimension)
        return score

    def score_sql(self, sql: str) -> tuple[float, list[str]]:
        score, reasons = self._registry.evaluate_phase2(
            sql=sql,
            conditions=[],
            table_metadata=self.table_metadata,
            field_distributions=self.field_distributions,
        )
        return score, reasons

    def score_branch(
        self,
        sql: str,
        active_conditions: list[str],
        risk_flags: list[str],
    ) -> tuple[float, list[str]]:
        score, reasons = self._registry.evaluate_phase2(
            sql=sql,
            conditions=active_conditions,
            table_metadata=self.table_metadata,
            field_distributions=self.field_distributions,
        )
        if risk_flags:
            reasons.extend(f"flag:{flag}" for flag in risk_flags)
        return score, self._dedupe_reasons(reasons)

    @staticmethod
    def _dedupe_reasons(reasons: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for r in reasons:
            if r and r not in seen:
                seen.add(r)
                out.append(r)
        return out
