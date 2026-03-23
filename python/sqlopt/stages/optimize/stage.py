"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

from sqlopt.common.llm_mock_generator import MockLLMProvider
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.stages.base import Stage


class OptimizeStage(Stage[None, OptimizeOutput]):
    """Optimize stage generates optimization proposals for SQL queries."""

    def __init__(self) -> None:
        super().__init__("optimize")
        self.mock_llm = MockLLMProvider()

    def run(self, _input_data: None = None) -> OptimizeOutput:
        return OptimizeOutput(
            proposals=[
                OptimizationProposal(
                    sql_unit_id="stub-1",
                    path_id="p1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id, name FROM users",
                    rationale="Reduce columns to improve performance",
                    confidence=0.9,
                )
            ]
        )
