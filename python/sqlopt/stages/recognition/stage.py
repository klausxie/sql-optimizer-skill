"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)


def _resolve_mybatis_params_for_explain(sql: str) -> str:
    """Replace MyBatis #{} params with sample values for EXPLAIN execution.

    Database EXPLAIN requires actual parameter values, not placeholders.
    This function replaces #{} with sample values suitable for EXPLAIN.
    """

    def get_sample_value(match: re.Match) -> str:
        param_name = match.group(1).lower()
        if any(k in param_name for k in ["id", "num", "count", "page", "size", "limit", "offset"]):
            return "1"
        if any(k in param_name for k in ["status", "type", "mode", "state"]):
            return "'active'"
        if any(k in param_name for k in ["name", "email", "title", "desc", "keyword"]):
            return "'test'"
        if any(k in param_name for k in ["date", "time", "start", "end"]):
            return "'2024-01-01'"
        return "1"

    return re.sub(r"#\{([^}]+)\}", get_sample_value, sql)


class RecognitionStage(Stage[None, RecognitionOutput]):
    """Recognition stage identifies performance baselines for SQL units."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
    ) -> None:
        super().__init__("recognition")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
    ) -> RecognitionOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock

        if rid is None:
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)
        parse_file = loader.get_parse_sql_units_with_branches_path()

        if not parse_file.exists():
            return self._create_stub_output()

        parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))

        baselines: list[PerformanceBaseline] = []
        platform = "postgresql"

        for sql_unit in parse_data.sql_units_with_branches:
            for branch in sql_unit.branches:
                if not branch.is_valid:
                    continue
                try:
                    sql_for_explain = _resolve_mybatis_params_for_explain(branch.expanded_sql)
                    baseline_data = self.llm_provider.generate_baseline(sql_for_explain, platform)
                    baseline = PerformanceBaseline(
                        sql_unit_id=sql_unit.sql_unit_id,
                        path_id=branch.path_id,
                        plan=baseline_data["plan"],
                        estimated_cost=baseline_data["estimated_cost"],
                        actual_time_ms=baseline_data.get("actual_time_ms"),
                    )
                    baselines.append(baseline)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Failed to generate baseline for %s: %s",
                        sql_unit.sql_unit_id,
                        str(e),
                    )
                    continue

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
