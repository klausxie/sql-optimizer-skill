"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

from pathlib import Path

from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage


class RecognitionStage(Stage[None, RecognitionOutput]):
    """Recognition stage identifies performance baselines for SQL units."""

    def __init__(
        self, run_id: str | None = None, llm_provider: LLMProviderBase | None = None
    ) -> None:
        super().__init__("recognition")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()

    def run(self, _input_data: None = None, run_id: str | None = None) -> RecognitionOutput:
        rid = run_id or self.run_id
        if rid is None:
            return self._create_stub_output()

        parse_file = Path("runs") / rid / "parse" / "sql_units_with_branches.json"
        if not parse_file.exists():
            return self._create_stub_output()

        parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))

        baselines: list[PerformanceBaseline] = []
        platform = "postgresql"

        for sql_unit in parse_data.sql_units_with_branches:
            for branch in sql_unit.branches:
                if not branch.is_valid:
                    continue
                baseline_data = self.llm_provider.generate_baseline(branch.expanded_sql, platform)
                baseline = PerformanceBaseline(
                    sql_unit_id=sql_unit.sql_unit_id,
                    path_id=branch.path_id,
                    plan=baseline_data["plan"],
                    estimated_cost=baseline_data["estimated_cost"],
                    actual_time_ms=baseline_data.get("actual_time_ms"),
                )
                baselines.append(baseline)

        output = RecognitionOutput(baselines=baselines)
        self._write_output(rid, output)
        return output

    def _create_stub_output(self) -> RecognitionOutput:
        baseline = PerformanceBaseline(
            sql_unit_id="stub-1",
            path_id="p1",
            plan={"cost": 100.0, "rows": 1000},
            estimated_cost=100.0,
            actual_time_ms=50.0,
        )
        return RecognitionOutput(baselines=[baseline])

    def _write_output(self, run_id: str, output: RecognitionOutput) -> None:
        output_dir = Path("runs") / run_id / "recognition"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "baselines.json"
        output_file.write_text(output.to_json(), encoding="utf-8")
