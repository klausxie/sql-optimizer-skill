"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

import json
from pathlib import Path

from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.stages.base import Stage


class OptimizeStage(Stage[None, OptimizeOutput]):
    """Optimize stage generates optimization proposals for SQL queries."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
    ) -> None:
        super().__init__("optimize")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
    ) -> OptimizeOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock

        if rid is None:
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)
        baselines_file = loader.get_recognition_baselines_path()

        if not baselines_file.exists():
            return self._create_stub_output()

        baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))

        parse_file = loader.get_parse_sql_units_with_branches_path()
        parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))

        # Build a lookup from (sql_unit_id, path_id) -> expanded_sql
        sql_lookup: dict[tuple[str, str], str] = {}
        for unit in parse_data.sql_units_with_branches:
            for branch in unit.branches:
                sql_lookup[(unit.sql_unit_id, branch.path_id)] = branch.expanded_sql

        proposals: list[OptimizationProposal] = []
        for baseline in baselines_data.baselines:
            sql = sql_lookup.get((baseline.sql_unit_id, baseline.path_id), "")
            if not sql:
                continue

            proposal_json = self.llm_provider.generate_optimization(sql, "")
            proposal_data = json.loads(proposal_json)

            proposal = OptimizationProposal(
                sql_unit_id=baseline.sql_unit_id,
                path_id=baseline.path_id,
                original_sql=sql,
                optimized_sql=proposal_data["optimized_sql"],
                rationale=proposal_data["rationale"],
                confidence=proposal_data["confidence"],
            )
            proposals.append(proposal)

        output = OptimizeOutput(proposals=proposals)
        self._write_output(rid, output)
        return output

    def _create_stub_output(self) -> OptimizeOutput:
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

    def _write_output(self, run_id: str, output: OptimizeOutput) -> None:
        output_dir = Path("runs") / run_id / "optimize"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "proposals.json"
        output_file.write_text(output.to_json(), encoding="utf-8")
