"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor, TaskResult
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)


class OptimizeStage(Stage[None, OptimizeOutput]):
    """Optimize stage generates optimization proposals for SQL queries."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
        config: SQLOptConfig | None = None,
    ) -> None:
        super().__init__("optimize")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config or SQLOptConfig()

    def run(
        self,
        input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
    ) -> OptimizeOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        logger.info("=" * 60)
        logger.info("[OPTIMIZE] Starting Optimize stage")
        logger.info(f"[OPTIMIZE] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[OPTIMIZE] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)
        baselines_file = loader.get_recognition_baselines_path()
        logger.info(f"[OPTIMIZE] Baselines file: {baselines_file}")

        if not baselines_file.exists():
            logger.warning(f"[OPTIMIZE] Baselines file not found: {baselines_file}, using stub data")
            return self._create_stub_output()

        baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))
        logger.info(f"[OPTIMIZE] Loaded {len(baselines_data.baselines)} baseline(s) from recognition stage")

        parse_file = loader.get_parse_sql_units_with_branches_path()
        parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))
        logger.info(f"[OPTIMIZE] Loaded {len(parse_data.sql_units_with_branches)} SQL unit(s) from parse stage")

        sql_lookup: dict[tuple[str, str], str] = {}
        for unit in parse_data.sql_units_with_branches:
            for branch in unit.branches:
                sql_lookup[(unit.sql_unit_id, branch.path_id)] = branch.expanded_sql

        proposals: list[OptimizationProposal] = []
        logger.info(f"[OPTIMIZE] Processing {len(baselines_data.baselines)} baseline(s) for optimization")

        if self.config.concurrency.enabled:
            proposals = self._run_concurrent(baselines_data.baselines, sql_lookup)
        else:
            proposals = self._run_sequential(baselines_data.baselines, sql_lookup)

        logger.info(f"[OPTIMIZE] Generated {len(proposals)} proposal(s)")
        output = OptimizeOutput(proposals=proposals)
        self._write_output(rid, output)
        logger.info(f"[OPTIMIZE] Output written to: runs/{rid}/optimize/proposals.json")
        logger.info("[OPTIMIZE] Optimize stage completed")
        return output

    def _run_sequential(
        self,
        baselines: list,
        sql_lookup: dict[tuple[str, str], str],
    ) -> list[OptimizationProposal]:
        proposals: list[OptimizationProposal] = []
        for baseline in baselines:
            sql = sql_lookup.get((baseline.sql_unit_id, baseline.path_id), "")
            if not sql:
                logger.debug(f"[OPTIMIZE]   Skipping {baseline.sql_unit_id}.{baseline.path_id} - no SQL found")
                continue

            try:
                logger.debug(f"[OPTIMIZE]   Generating optimization for {baseline.sql_unit_id}.{baseline.path_id}")
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
                logger.info(
                    f"[OPTIMIZE]   ✓ {baseline.sql_unit_id}.{baseline.path_id}: confidence={proposal_data['confidence']:.2f}"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "[OPTIMIZE]   ✗ Failed: %s.%s - %s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    str(e),
                )
                continue
        return proposals

    def _run_concurrent(
        self,
        baselines: list,
        sql_lookup: dict[tuple[str, str], str],
    ) -> list[OptimizationProposal]:
        tasks = []
        for baseline in baselines:
            sql = sql_lookup.get((baseline.sql_unit_id, baseline.path_id), "")
            if sql:
                tasks.append((baseline, sql))

        if not tasks:
            return []

        options = BatchOptions(
            max_workers=self.config.concurrency.max_workers,
            max_concurrent=self.config.concurrency.llm_max_concurrent,
            timeout_per_task=self.config.concurrency.timeout_per_task,
            retry_count=self.config.concurrency.retry_count,
            retry_delay=float(self.config.concurrency.retry_delay),
        )

        proposals: list[OptimizationProposal] = []
        total = len(tasks)
        completed = 0

        def process_task(task: tuple) -> OptimizationProposal | None:
            baseline, sql = task
            proposal_json = self.llm_provider.generate_optimization(sql, "")
            proposal_data = json.loads(proposal_json)
            return OptimizationProposal(
                sql_unit_id=baseline.sql_unit_id,
                path_id=baseline.path_id,
                original_sql=sql,
                optimized_sql=proposal_data["optimized_sql"],
                rationale=proposal_data["rationale"],
                confidence=proposal_data["confidence"],
            )

        with ConcurrentExecutor(options) as executor:
            results = executor.map(process_task, tasks)

        for result in results:
            completed += 1
            if result.success and result.result:
                proposals.append(result.result)
                logger.info(
                    f"[OPTIMIZE]   ✓ {result.result.sql_unit_id}.{result.result.path_id} "
                    f"({completed}/{total}): confidence={result.result.confidence:.2f}"
                )
            else:
                baseline = result.item[0]
                logger.warning(
                    f"[OPTIMIZE]   ✗ {baseline.sql_unit_id}.{baseline.path_id} ({completed}/{total}): {result.error}"
                )

        return proposals

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
