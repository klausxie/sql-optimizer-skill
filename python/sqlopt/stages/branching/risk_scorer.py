from __future__ import annotations

from dataclasses import dataclass

from sqlopt.stages.branching.branch_strategy import LadderSamplingStrategy
from sqlopt.stages.branching.dimension_extractor import BranchDimension


@dataclass
class SQLDeltaRiskScorer:
    """Score branch dimensions using their SQL fragment delta."""

    table_metadata: dict[str, dict] | None = None

    def __post_init__(self) -> None:
        self._strategy = LadderSamplingStrategy(table_metadata=self.table_metadata or {})

    def score_dimension(self, dimension: BranchDimension) -> float:
        fragment = dimension.sql_fragment.strip()
        if fragment:
            score = self._strategy._get_condition_weight(fragment)
        else:
            score = self._strategy._get_condition_weight(dimension.condition)

        # Slightly boost deeper nested branches because they are often harder
        # to reason about and more likely to be missed by naive sampling.
        score += dimension.depth * 0.25
        return score
