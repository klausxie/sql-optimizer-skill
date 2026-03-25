"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor, TaskResult
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage

if TYPE_CHECKING:
    from sqlopt.common.config import SQLOptConfig

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
        config: SQLOptConfig | None = None,
    ) -> None:
        super().__init__("recognition")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config

    def run(
        self,
        input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
    ) -> RecognitionOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        logger.info("=" * 60)
        logger.info("[RECOGNITION] Starting Recognition stage")
        logger.info(f"[RECOGNITION] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[RECOGNITION] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)
        parse_file = loader.get_parse_sql_units_with_branches_path()
        logger.info(f"[RECOGNITION] Parse file: {parse_file}")

        if not parse_file.exists():
            logger.warning(f"[RECOGNITION] Parse file not found: {parse_file}, using stub data")
            return self._create_stub_output()

        parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))
        logger.info(f"[RECOGNITION] Loaded {len(parse_data.sql_units_with_branches)} SQL unit(s) from parse stage")

        if self.config and self.config.concurrency.enabled:
            logger.info("[RECOGNITION] Using concurrent execution mode")
            baselines = self._run_concurrent(parse_data)
        else:
            baselines = self._run_sequential(parse_data)

        logger.info(f"[RECOGNITION] Generated {len(baselines)} baseline(s)")
        output = RecognitionOutput(baselines=baselines)
        self._write_output(rid, output)
        logger.info(f"[RECOGNITION] Output written to: runs/{rid}/recognition/baselines.json")
        logger.info("[RECOGNITION] Recognition stage completed")
        return output

    def _run_sequential(self, parse_data: ParseOutput) -> list[PerformanceBaseline]:
        baselines: list[PerformanceBaseline] = []
        platform = "postgresql"
        total_branches = sum(len(su.branches) for su in parse_data.sql_units_with_branches)
        logger.info(f"[RECOGNITION] Processing {total_branches} branch(es) for baseline generation")

        for sql_unit in parse_data.sql_units_with_branches:
            for branch in sql_unit.branches:
                if not branch.is_valid:
                    logger.debug(f"[RECOGNITION]   Skipping invalid branch: {branch.path_id}")
                    continue
                try:
                    sql_for_explain = _resolve_mybatis_params_for_explain(branch.expanded_sql)
                    logger.debug(
                        f"[RECOGNITION]   EXPLAIN for {sql_unit.sql_unit_id}.{branch.path_id}: {sql_for_explain[:60]}..."
                    )
                    baseline_data = self.llm_provider.generate_baseline(sql_for_explain, platform)
                    baseline = PerformanceBaseline(
                        sql_unit_id=sql_unit.sql_unit_id,
                        path_id=branch.path_id,
                        plan=baseline_data["plan"],
                        estimated_cost=baseline_data["estimated_cost"],
                        actual_time_ms=baseline_data.get("actual_time_ms"),
                    )
                    baselines.append(baseline)
                    logger.info(
                        f"[RECOGNITION]   ✓ {sql_unit.sql_unit_id}.{branch.path_id}: cost={baseline_data['estimated_cost']}"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "[RECOGNITION]   ✗ Failed: %s.%s - %s",
                        sql_unit.sql_unit_id,
                        branch.path_id,
                        str(e),
                    )
                    continue

        return baselines

    def _run_concurrent(self, parse_data: ParseOutput) -> list[PerformanceBaseline]:
        tasks: list[tuple[str, str, str]] = [
            (sql_unit.sql_unit_id, branch.path_id, branch.expanded_sql)
            for sql_unit in parse_data.sql_units_with_branches
            for branch in sql_unit.branches
            if branch.is_valid
        ]

        total = len(tasks)
        logger.info(f"[RECOGNITION] Processing {total} branch(es) concurrently")

        options = BatchOptions(
            max_workers=self.config.concurrency.max_workers if self.config else 4,
            timeout_per_task=self.config.concurrency.timeout_per_task if self.config else 120,
        )
        baselines: list[PerformanceBaseline] = []
        platform = "postgresql"

        def process_task(task: tuple[str, str, str]) -> PerformanceBaseline | None:
            sql_unit_id, path_id, expanded_sql = task
            sql_for_explain = _resolve_mybatis_params_for_explain(expanded_sql)
            baseline_data = self.llm_provider.generate_baseline(sql_for_explain, platform)
            return PerformanceBaseline(
                sql_unit_id=sql_unit_id,
                path_id=path_id,
                plan=baseline_data["plan"],
                estimated_cost=baseline_data["estimated_cost"],
                actual_time_ms=baseline_data.get("actual_time_ms"),
            )

        completed = [0]

        def on_progress(done: int, total_count: int) -> None:
            completed[0] = done
            logger.info(f"[RECOGNITION] Progress: {done}/{total_count}")

        with ConcurrentExecutor(options) as executor:
            results: list[TaskResult] = executor.map(process_task, tasks, on_progress)

        for result in results:
            if result.success and result.result:
                baselines.append(result.result)
                logger.info(
                    f"[RECOGNITION]   ✓ {result.result.sql_unit_id}.{result.result.path_id}: "
                    f"cost={result.result.estimated_cost}"
                )
            else:
                logger.warning(f"[RECOGNITION]   ✗ Failed: {result.error}")

        return baselines

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
