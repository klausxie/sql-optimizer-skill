"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor, TaskResult
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.contracts.init import TableSchema
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage

if TYPE_CHECKING:
    from sqlopt.common.config import SQLOptConfig

logger = logging.getLogger(__name__)


def _resolve_mybatis_params_for_explain(sql: str, table_schemas: dict[str, TableSchema] | None = None) -> str:
    """Replace MyBatis #{} params with sample values for EXPLAIN execution.

    Database EXPLAIN requires actual parameter values, not placeholders.
    This function replaces #{} with sample values suitable for EXPLAIN.
    When table_schemas is provided, uses column type information for correct values.
    """

    def camel_to_snake(name: str) -> str:
        result = []
        for i, c in enumerate(name):
            if c.isupper() and i > 0:
                result.append("_")
            result.append(c.lower())
        return "".join(result)

    def get_column_type_from_context(param_name: str, sql_lower: str) -> str | None:
        if not table_schemas:
            return None
        param_lower = param_name.lower()
        param_snake = camel_to_snake(param_name)
        for table_name, schema in table_schemas.items():
            table_lower = table_name.lower()
            table_pattern = rf"\b{re.escape(table_lower)}\b"
            if not re.search(table_pattern, sql_lower):
                continue
            for col in schema.columns:
                col_name = col.get("name", "").lower()
                col_type = col.get("type", "").upper()
                if col_name == param_lower or col_name == param_snake:
                    return col_type
        return None

    def get_sample_value(match: re.Match) -> str:
        param_name = match.group(1).split(".")[0]
        param_lower = param_name.lower()
        sql_lower = sql.lower()
        col_type = get_column_type_from_context(param_name, sql_lower)
        if col_type:
            if any(
                t in col_type
                for t in ["INT", "BIGINT", "SMALLINT", "TINYINT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "SERIAL"]
            ):
                return "1"
            if any(t in col_type for t in ["BOOL"]):
                return "true"
            if any(t in col_type for t in ["DATE"]):
                return "'2024-01-01'"
            if any(t in col_type for t in ["TIME", "TIMESTAMP"]):
                return "'2024-01-01 00:00:00'"
            return "'test'"
        if any(k in param_lower for k in ["id", "num", "count", "page", "size", "limit", "offset"]):
            return "1"
        if any(k in param_lower for k in ["status", "type", "mode", "state"]):
            return "1"
        if any(k in param_lower for k in ["name", "email", "title", "desc", "keyword"]):
            return "'test'"
        if any(k in param_lower for k in ["date", "time", "start", "end"]):
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

        table_schemas: dict[str, TableSchema] | None = None
        table_schemas_file = loader.get_init_table_schemas_path()
        if table_schemas_file.exists():
            try:
                import json

                from sqlopt.contracts.init import TableSchema

                schemas_data = json.loads(table_schemas_file.read_text(encoding="utf-8"))
                table_schemas = {k: TableSchema(**v) for k, v in schemas_data.items()}
                logger.info(f"[RECOGNITION] Loaded {len(table_schemas)} table schema(s)")
            except Exception:
                logger.debug("[RECOGNITION] Failed to load table schemas, using heuristics")

        start_time = time.time()
        if self.config and self.config.concurrency.enabled:
            logger.info("[RECOGNITION] Using concurrent execution mode")
            baselines = self._run_concurrent(parse_data, table_schemas)
        else:
            baselines = self._run_sequential(parse_data, table_schemas)

        duration_seconds = time.time() - start_time
        logger.info(f"[RECOGNITION] Generated {len(baselines)} baseline(s)")
        output = RecognitionOutput(baselines=baselines)
        file_stats = self._write_output(rid, output)
        self._write_summary(rid, output, duration_seconds, file_stats)
        logger.info("[RECOGNITION] Recognition stage completed")
        return output

    def _run_sequential(
        self, parse_data: ParseOutput, table_schemas: dict[str, TableSchema] | None
    ) -> list[PerformanceBaseline]:
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
                    sql_for_explain = _resolve_mybatis_params_for_explain(branch.expanded_sql, table_schemas)
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
                        "[RECOGNITION]   [OK] %s.%s: cost=%s",
                        sql_unit.sql_unit_id,
                        branch.path_id,
                        baseline_data["estimated_cost"],
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "[RECOGNITION]   [FAIL] Failed: %s.%s - %s",
                        sql_unit.sql_unit_id,
                        branch.path_id,
                        str(e),
                    )
                    continue

        return baselines

    def _run_concurrent(
        self, parse_data: ParseOutput, table_schemas: dict[str, TableSchema] | None
    ) -> list[PerformanceBaseline]:
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
            sql_for_explain = _resolve_mybatis_params_for_explain(expanded_sql, table_schemas)
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
                    "[RECOGNITION]   [OK] %s.%s: cost=%s",
                    result.result.sql_unit_id,
                    result.result.path_id,
                    result.result.estimated_cost,
                )
            else:
                logger.warning("[RECOGNITION]   [FAIL] Failed: %s", result.error)

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

    def _write_output(self, run_id: str, output: RecognitionOutput) -> dict:
        """Write recognition output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/recognition/units/{unit_id}.json (per unit, grouped baselines)
        - runs/{run_id}/recognition/units/_index.json (unit ID list)
        - runs/{run_id}/recognition/baselines.json (backward compat)

        Returns:
            dict with 'unit_count', 'file_size_bytes' keys
        """
        if not output.baselines:
            logger.debug("[RECOGNITION] No baselines to write, skipping file output")
            return {"unit_count": 0, "file_size_bytes": 0}

        file_manager = ContractFileManager(run_id, "recognition")

        # Group baselines by sql_unit_id
        baselines_by_unit: dict[str, list[dict]] = {}
        for baseline in output.baselines:
            unit_id = baseline.sql_unit_id
            if unit_id not in baselines_by_unit:
                baselines_by_unit[unit_id] = []
            baselines_by_unit[unit_id].append(
                {
                    "sql_unit_id": baseline.sql_unit_id,
                    "path_id": baseline.path_id,
                    "plan": baseline.plan,
                    "estimated_cost": baseline.estimated_cost,
                    "actual_time_ms": baseline.actual_time_ms,
                }
            )

        unit_ids: list[str] = []
        total_bytes = 0

        for unit_id, baselines in baselines_by_unit.items():
            unit_data = {"sql_unit_id": unit_id, "baselines": baselines}
            path = file_manager.write_unit_file(unit_id, unit_data)
            total_bytes += file_manager.get_file_size(path)
            unit_ids.append(unit_id)

        index_path = file_manager.write_index(unit_ids)
        total_bytes += file_manager.get_file_size(index_path)

        # Write backward-compatible single file
        output_dir = Path("runs") / run_id / "recognition"
        output_dir.mkdir(parents=True, exist_ok=True)
        compat_path = output_dir / "baselines.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")
        compat_bytes = file_manager.get_file_size(compat_path)

        logger.info(
            f"[RECOGNITION] Wrote {len(unit_ids)} unit file(s) ({total_bytes} bytes) "
            f"+ index + compat file ({compat_bytes} bytes)"
        )
        return {"unit_count": len(unit_ids), "file_size_bytes": total_bytes + compat_bytes}

    def _write_summary(self, run_id: str, output: RecognitionOutput, duration_seconds: float, file_stats: dict) -> None:
        try:
            unique_units = {b.sql_unit_id for b in output.baselines}
            summary = StageSummary(
                stage_name="recognition",
                run_id=run_id,
                duration_seconds=duration_seconds,
                sql_units_count=len(unique_units),
                branches_count=len(output.baselines),
                files_count=file_stats["unit_count"] + 2,
                file_size_bytes=file_stats["file_size_bytes"],
            )
            content = generate_summary_markdown(summary)
            output_dir = Path("runs") / run_id / "recognition"
            output_dir.mkdir(parents=True, exist_ok=True)
            summary_path = output_dir / "SUMMARY.md"
            summary_path.write_text(content, encoding="utf-8")
            logger.info(f"[RECOGNITION] Wrote SUMMARY.md ({len(content)} chars)")
        except Exception:  # noqa: BLE001
            logger.warning("[RECOGNITION] Failed to write SUMMARY.md, continuing")
