"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.runtime_factory import create_db_connector_from_config
from sqlopt.common.summary_generator import generate_optimize_summary_markdown
from sqlopt.contracts.init import TableSchema
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage
from sqlopt.stages.recognition.stage import (
    _build_result_signature,
    _extract_rows_examined,
    _is_select_statement,
    _normalize_baseline_data,
    _resolve_mybatis_params_for_explain,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


class OptimizeStage(Stage[None, OptimizeOutput]):
    """Optimize stage generates optimization proposals for SQL queries."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
        config: SQLOptConfig | None = None,
        db_connector: Any | None = None,
        base_dir: str = "./runs",
    ) -> None:
        super().__init__("optimize", base_dir=base_dir)
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config or SQLOptConfig()
        self.db_connector = db_connector or getattr(self.llm_provider, "db_connector", None)

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> OptimizeOutput:
        start_time = time.time()
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        self._progress_callback = progress_callback
        logger.info("=" * 60)
        logger.info("[OPTIMIZE] Starting Optimize stage")
        logger.info(f"[OPTIMIZE] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[OPTIMIZE] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        baselines_file = loader.get_recognition_baselines_path()
        logger.info(f"[OPTIMIZE] Baselines file: {baselines_file}")

        if not baselines_file.exists():
            logger.warning(f"[OPTIMIZE] Baselines file not found: {baselines_file}, using stub data")
            return self._create_stub_output()

        baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))
        logger.info(f"[OPTIMIZE] Loaded {len(baselines_data.baselines)} baseline(s) from recognition stage")

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        table_schemas = self._load_table_schemas(loader)
        db_connector = self._get_db_connector()

        proposals: list[OptimizationProposal] = []
        logger.info(f"[OPTIMIZE] Processing {len(baselines_data.baselines)} baseline(s) for optimization")

        try:
            if self.config.concurrency.enabled and db_connector is None:
                proposals = self._run_concurrent(baselines_data.baselines, self._progress_callback, table_schemas)
            else:
                if db_connector is not None and self.config.concurrency.enabled:
                    logger.info("[OPTIMIZE] DB validation enabled, forcing sequential execution")
                proposals = self._run_sequential(baselines_data.baselines, self._progress_callback, table_schemas)
        finally:
            self._disconnect_db_connector()

        logger.info(f"[OPTIMIZE] Generated {len(proposals)} proposal(s)")
        output = OptimizeOutput(proposals=proposals, run_id=rid)
        self._write_output(rid, output)
        logger.info(f"[OPTIMIZE] Output written to: runs/{rid}/optimize/proposals.json")

        # Generate SUMMARY.md (best-effort, don't block on failure)
        self._generate_summary(rid, output, start_time)

        logger.info("[OPTIMIZE] Optimize stage completed")
        return output

    def _run_sequential(
        self,
        baselines: list[PerformanceBaseline],
        progress_callback: ProgressCallback | None,
        table_schemas: dict[str, TableSchema] | None,
    ) -> list[OptimizationProposal]:
        proposals: list[OptimizationProposal] = []
        for idx, baseline in enumerate(baselines):
            if progress_callback:
                progress_callback(
                    f"Optimizing {idx + 1}/{len(baselines)}: {baseline.sql_unit_id}.{baseline.path_id}",
                    (idx + 1, len(baselines)),
                )
            if baseline.plan is None:
                key = f"{baseline.sql_unit_id}.{baseline.path_id}"
                logger.info(f"[OPTIMIZE]   [SKIP] Skipping optimization for baseline_only (no plan): {key}")
                continue

            try:
                logger.debug(f"[OPTIMIZE]   Generating optimization for {baseline.sql_unit_id}.{baseline.path_id}")
                proposal_json = self.llm_provider.generate_optimization(baseline.original_sql, "")
                proposal_data = json.loads(proposal_json)
                validation = self._validate_optimized_sql(
                    baseline=baseline,
                    optimized_sql=proposal_data["optimized_sql"],
                    table_schemas=table_schemas,
                )

                proposal = OptimizationProposal(
                    sql_unit_id=baseline.sql_unit_id,
                    path_id=baseline.path_id,
                    original_sql=baseline.original_sql,
                    optimized_sql=proposal_data["optimized_sql"],
                    rationale=proposal_data["rationale"],
                    confidence=proposal_data["confidence"],
                    before_metrics=self._build_before_metrics(baseline),
                    after_metrics=validation["after_metrics"],
                    result_equivalent=validation["result_equivalent"],
                    validation_status=validation["validation_status"],
                    validation_error=validation["validation_error"],
                    gain_ratio=validation["gain_ratio"],
                )
                proposals.append(proposal)
                logger.info(
                    "[OPTIMIZE]   [OK] %s.%s: confidence=%.2f, status=%s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    proposal_data["confidence"],
                    validation["validation_status"],
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "[OPTIMIZE]   [FAIL] Failed: %s.%s - %s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    str(e),
                )
                continue
        return proposals

    def _run_concurrent(
        self,
        baselines: list[PerformanceBaseline],
        progress_callback: ProgressCallback | None,
        table_schemas: dict[str, TableSchema] | None,
    ) -> list[OptimizationProposal]:
        tasks = []
        for baseline in baselines:
            if baseline.plan is None:
                key = f"{baseline.sql_unit_id}.{baseline.path_id}"
                logger.info(f"[OPTIMIZE]   [SKIP] Skipping optimization for baseline_only (no plan): {key}")
                continue
            tasks.append(baseline)

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

        def process_task(baseline: PerformanceBaseline) -> OptimizationProposal:
            proposal_json = self.llm_provider.generate_optimization(baseline.original_sql, "")
            proposal_data = json.loads(proposal_json)
            validation = self._validate_optimized_sql(
                baseline=baseline,
                optimized_sql=proposal_data["optimized_sql"],
                table_schemas=table_schemas,
            )
            return OptimizationProposal(
                sql_unit_id=baseline.sql_unit_id,
                path_id=baseline.path_id,
                original_sql=baseline.original_sql,
                optimized_sql=proposal_data["optimized_sql"],
                rationale=proposal_data["rationale"],
                confidence=proposal_data["confidence"],
                before_metrics=self._build_before_metrics(baseline),
                after_metrics=validation["after_metrics"],
                result_equivalent=validation["result_equivalent"],
                validation_status=validation["validation_status"],
                validation_error=validation["validation_error"],
                gain_ratio=validation["gain_ratio"],
            )

        with ConcurrentExecutor(options) as executor:
            results = executor.map(process_task, tasks)

        for completed, result in enumerate(results, start=1):
            if result.success and result.result:
                proposals.append(result.result)
                if progress_callback:
                    progress_callback(
                        f"Optimizing {completed}/{total}: {result.result.sql_unit_id}.{result.result.path_id}",
                        (completed, total),
                    )
                logger.info(
                    "[OPTIMIZE]   [OK] %s.%s (%d/%d): confidence=%.2f, status=%s",
                    result.result.sql_unit_id,
                    result.result.path_id,
                    completed,
                    total,
                    result.result.confidence,
                    result.result.validation_status,
                )
            else:
                baseline = result.item
                if progress_callback:
                    progress_callback(
                        f"Optimizing {completed}/{total}: {baseline.sql_unit_id}.{baseline.path_id}",
                        (completed, total),
                    )
                logger.warning(
                    "[OPTIMIZE]   [FAIL] %s.%s (%d/%d): %s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    completed,
                    total,
                    result.error,
                )

        return proposals

    @staticmethod
    def _create_stub_output() -> OptimizeOutput:
        return OptimizeOutput(
            proposals=[
                OptimizationProposal(
                    sql_unit_id="stub-1",
                    path_id="p1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id, name FROM users",
                    rationale="Reduce columns to improve performance",
                    confidence=0.9,
                    before_metrics={"estimated_cost": 100.0, "actual_time_ms": 50.0},
                    after_metrics={"estimated_cost": 20.0, "actual_time_ms": 10.0},
                    result_equivalent=True,
                    validation_status="validated",
                    gain_ratio=0.8,
                )
            ],
            run_id="stub",
        )

    @staticmethod
    def _load_table_schemas(loader: MockDataLoader) -> dict[str, TableSchema]:
        schemas: dict[str, TableSchema] = {}
        schemas_file = loader.get_init_table_schemas_path()
        if not schemas_file.exists():
            return schemas
        try:
            schemas_data = json.loads(schemas_file.read_text(encoding="utf-8"))
            schemas = {name: TableSchema(**item) for name, item in schemas_data.items()}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.debug("[OPTIMIZE] Failed to load table schemas, using heuristics")
        return schemas

    def _get_db_connector(self) -> Any | None:
        if self.db_connector is not None:
            return self.db_connector

        if self.config and self.config.db_host and self.config.db_port and self.config.db_name:
            self.db_connector = create_db_connector_from_config(self.config)
        return self.db_connector

    def _disconnect_db_connector(self) -> None:
        connector = self.db_connector
        if connector is None or not hasattr(connector, "disconnect"):
            return
        try:
            connector.disconnect()
        except Exception:
            logger.debug("[OPTIMIZE] Failed to disconnect DB connector", exc_info=True)

    @staticmethod
    def _build_before_metrics(baseline: PerformanceBaseline) -> dict:
        return {
            "estimated_cost": baseline.estimated_cost,
            "actual_time_ms": baseline.actual_time_ms,
            "rows_returned": baseline.rows_returned,
            "rows_examined": baseline.rows_examined,
            "result_signature": baseline.result_signature,
            "plan": baseline.plan,
        }

    def _validate_optimized_sql(
        self,
        baseline: PerformanceBaseline,
        optimized_sql: str,
        table_schemas: dict[str, TableSchema] | None,
    ) -> dict[str, Any]:
        after_metrics: dict[str, Any] = {
            "estimated_cost": None,
            "actual_time_ms": None,
            "rows_returned": None,
            "rows_examined": None,
            "result_signature": None,
            "plan": None,
        }
        validation_status = "not_validated"
        validation_error = None
        result_equivalent = None

        executable_sql = _resolve_mybatis_params_for_explain(optimized_sql, table_schemas)
        db_connector = self.db_connector

        try:
            if db_connector is not None:
                baseline_data = _normalize_baseline_data(db_connector.execute_explain(executable_sql))
            else:
                baseline_data = _normalize_baseline_data(
                    self.llm_provider.generate_baseline(executable_sql, self.config.db_platform)
                )
        except Exception as e:  # noqa: BLE001
            return {
                "after_metrics": after_metrics,
                "validation_status": "validation_failed",
                "validation_error": f"explain_failed: {e}",
                "result_equivalent": None,
                "gain_ratio": None,
            }

        after_metrics["estimated_cost"] = baseline_data.get("estimated_cost")
        after_metrics["actual_time_ms"] = baseline_data.get("actual_time_ms")
        after_metrics["plan"] = baseline_data.get("plan")
        after_metrics["rows_examined"] = _extract_rows_examined(after_metrics["plan"])

        if db_connector is None:
            validation_status = "estimated_only"
            return {
                "after_metrics": after_metrics,
                "validation_status": validation_status,
                "validation_error": None,
                "result_equivalent": None,
                "gain_ratio": self._calculate_gain_ratio(
                    baseline.actual_time_ms,
                    baseline.estimated_cost,
                    after_metrics["actual_time_ms"],
                    after_metrics["estimated_cost"],
                ),
            }

        if not _is_select_statement(executable_sql):
            validation_status = "explained_only"
            return {
                "after_metrics": after_metrics,
                "validation_status": validation_status,
                "validation_error": None,
                "result_equivalent": None,
                "gain_ratio": self._calculate_gain_ratio(
                    baseline.actual_time_ms,
                    baseline.estimated_cost,
                    after_metrics["actual_time_ms"],
                    after_metrics["estimated_cost"],
                ),
            }

        try:
            query_started_at = time.perf_counter()
            rows = db_connector.execute_query(executable_sql)
            after_metrics["actual_time_ms"] = (time.perf_counter() - query_started_at) * 1000.0
            after_metrics["rows_returned"] = len(rows)
            after_metrics["result_signature"] = _build_result_signature(rows)
            expected_signature = baseline.result_signature
            if expected_signature is not None:
                result_equivalent = expected_signature == after_metrics["result_signature"]
                validation_status = "validated" if result_equivalent else "result_mismatch"
            else:
                validation_status = "validated_without_baseline"
        except Exception as e:  # noqa: BLE001
            validation_status = "validation_failed"
            validation_error = f"query_execution_failed: {e}"

        return {
            "after_metrics": after_metrics,
            "validation_status": validation_status,
            "validation_error": validation_error,
            "result_equivalent": result_equivalent,
            "gain_ratio": self._calculate_gain_ratio(
                baseline.actual_time_ms,
                baseline.estimated_cost,
                after_metrics["actual_time_ms"],
                after_metrics["estimated_cost"],
            ),
        }

    @staticmethod
    def _calculate_gain_ratio(
        before_time_ms: float | None,
        before_cost: float | None,
        after_time_ms: float | None,
        after_cost: float | None,
    ) -> float | None:
        if before_time_ms and after_time_ms is not None and before_time_ms > 0:
            return (before_time_ms - after_time_ms) / before_time_ms
        if before_cost and after_cost is not None and before_cost > 0:
            return (before_cost - after_cost) / before_cost
        return None

    def _write_output(self, run_id: str, output: OptimizeOutput) -> None:
        """Write optimize output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/optimize/units/{unit_id}.json (per unit)
        - runs/{run_id}/optimize/units/_index.json (unit ID list)
        - runs/{run_id}/optimize/proposals.json (backward compat)
        """
        output_dir = self.resolve_run_paths(run_id).optimize_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Always write backward-compatible proposals.json
        compat_path = output_dir / "proposals.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")

        if not output.proposals:
            logger.debug("[OPTIMIZE] No proposals to write, wrote empty proposals.json")
            return

        file_manager = ContractFileManager(run_id, "optimize", base_dir=self.base_dir)

        proposals_by_unit: dict[str, list[dict]] = {}
        for proposal in output.proposals:
            if proposal.sql_unit_id not in proposals_by_unit:
                proposals_by_unit[proposal.sql_unit_id] = []
            proposals_by_unit[proposal.sql_unit_id].append(
                {
                    "sql_unit_id": proposal.sql_unit_id,
                    "path_id": proposal.path_id,
                    "original_sql": proposal.original_sql,
                    "optimized_sql": proposal.optimized_sql,
                    "rationale": proposal.rationale,
                    "confidence": proposal.confidence,
                    "before_metrics": proposal.before_metrics,
                    "after_metrics": proposal.after_metrics,
                    "result_equivalent": proposal.result_equivalent,
                    "validation_status": proposal.validation_status,
                    "validation_error": proposal.validation_error,
                    "gain_ratio": proposal.gain_ratio,
                }
            )

        unit_ids: list[str] = []
        total_bytes = 0
        for unit_id, proposals in proposals_by_unit.items():
            unit_data = {
                "sql_unit_id": unit_id,
                "proposals": proposals,
            }
            path = file_manager.write_unit_file(unit_id, unit_data)
            total_bytes += file_manager.get_file_size(path)
            unit_ids.append(unit_id)

        # Write index
        index_path = file_manager.write_index(unit_ids)
        total_bytes += file_manager.get_file_size(index_path)

        compat_bytes = file_manager.get_file_size(compat_path)

        logger.info(
            f"[OPTIMIZE] Wrote {len(unit_ids)} unit file(s) ({total_bytes} bytes) "
            f"+ index + compat file ({compat_bytes} bytes)"
        )

    def _generate_summary(
        self,
        run_id: str,
        output: OptimizeOutput,
        start_time: float,
    ) -> None:
        """Generate SUMMARY.md for the optimize stage.

        Best-effort operation - errors are logged but don't block stage completion.
        """
        try:
            duration_seconds = time.time() - start_time

            output_dir = self.resolve_run_paths(run_id).optimize_dir
            file_size_bytes = 0
            files_count = 0

            if output_dir.exists():
                for file_path in output_dir.rglob("*.json"):
                    if file_path.is_file():
                        file_size_bytes += file_path.stat().st_size
                        files_count += 1

            output_with_run_id = OptimizeOutput(
                proposals=output.proposals,
                run_id=run_id,
            )

            markdown = generate_optimize_summary_markdown(
                output=output_with_run_id,
                duration_seconds=duration_seconds,
                file_size_bytes=file_size_bytes,
                files_count=files_count,
            )
            summary_path = output_dir / "SUMMARY.md"
            summary_path.write_text(markdown, encoding="utf-8")
            logger.info(f"[OPTIMIZE] SUMMARY.md written to: {summary_path}")

        except Exception as e:  # noqa: BLE001
            logger.warning(f"[OPTIMIZE] Failed to generate SUMMARY.md: {e}")
