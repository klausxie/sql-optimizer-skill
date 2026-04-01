"""Risk scoring for branch dimensions and rendered SQL.

This module delegates all risk detection to RiskRuleRegistry.
The public API (score_dimension, score_sql, score_branch) is unchanged
so existing callers see no difference in behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlopt.common.risk_assessment import Domain, ImpactType, RiskAssessment, RiskFactor, Severity
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
    ) -> RiskAssessment:
        return self._score_assessment(sql, active_conditions, risk_flags)

    def _score_assessment(
        self,
        sql: str,
        conditions: list[str],
        risk_flags: list[str],
    ) -> RiskAssessment:
        factors, _raw_score = self._registry.evaluate_phase2_factors(
            sql,
            conditions,
            self.table_metadata,
            self.field_distributions,
        )

        for cond in conditions:
            factors.append(
                RiskFactor(
                    code="ACTIVE_CONDITION",
                    severity=Severity.INFO,
                    domain=Domain.SYNTACTIC,
                    weight=0.5,
                    explanation_template=f"Active condition: {cond}",
                    impact_type=ImpactType.IO_SPIKE,
                    remediation_template="This is a trace of active MyBatis conditions, not a risk.",
                )
            )

        for flag in risk_flags:
            factors.append(
                RiskFactor(
                    code=f"RISK_FLAG_{flag.upper()}",
                    severity=Severity.WARNING,
                    domain=Domain.SYNTACTIC,
                    weight=1.0,
                    explanation_template=f"Risk flag: {flag}",
                    impact_type=ImpactType.IO_SPIKE,
                    remediation_template="Review this risk flag in context.",
                )
            )

        return RiskAssessment(factors=factors)
