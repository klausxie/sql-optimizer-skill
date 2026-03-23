"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage


class RecognitionStage(Stage[None, RecognitionOutput]):
    """Recognition stage identifies performance baselines for SQL units."""

    def __init__(self) -> None:
        super().__init__("recognition")

    def run(self, _input_data: None = None) -> RecognitionOutput:
        baseline = PerformanceBaseline(
            sql_unit_id="stub-1",
            path_id="p1",
            plan={"cost": 100.0, "rows": 1000},
            estimated_cost=100.0,
            actual_time_ms=50.0,
        )
        return RecognitionOutput(baselines=[baseline])
