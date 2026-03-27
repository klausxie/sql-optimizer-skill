"""Recognition stage for SQL performance baseline identification."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Callable

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor, TaskResult
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.runtime_factory import create_db_connector_from_config
from sqlopt.common.summary_generator import (
    generate_recognition_summary_markdown,
)
from sqlopt.contracts.init import TableSchema
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


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
                if col_name in (param_lower, param_snake):
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


def _is_select_statement(sql: str) -> bool:
    """Best-effort detection for read-only queries that can be safely executed."""
    sql_upper = sql.lstrip().upper()
    if sql_upper.startswith("SELECT"):
        return True
    if sql_upper.startswith("WITH"):
        return "SELECT" in sql_upper and "UPDATE" not in sql_upper and "DELETE" not in sql_upper
    return False


def _estimate_cost_from_plan(plan: dict | None) -> float:
    """Extract estimated cost from known plan formats."""
    if not isinstance(plan, dict):
        return 0.0
    if "Plan" in plan and isinstance(plan["Plan"], dict):
        return float(plan["Plan"].get("Total Cost", 0.0) or 0.0)
    query_block = plan.get("query_block", {})
    if isinstance(query_block, dict):
        cost_info = query_block.get("cost_info", {})
        if isinstance(cost_info, dict):
            return float(cost_info.get("query_cost", 0.0) or 0.0)
        return float(query_block.get("cost", 0.0) or 0.0)
    if "cost" in plan:
        return float(plan.get("cost", 0.0) or 0.0)
    return 0.0


def _extract_actual_time_ms(plan: dict | None) -> float | None:
    """Extract actual execution time from known plan formats."""
    if not isinstance(plan, dict):
        return None
    if "Plan" in plan and isinstance(plan["Plan"], dict):
        actual_total = plan["Plan"].get("Actual Total Time")
        return float(actual_total) if actual_total is not None else None
    return None


def _extract_rows_examined(plan: dict | None) -> int | None:
    """Best-effort extraction of examined row counts from plan trees."""
    if not isinstance(plan, dict):
        return None

    candidate_keys = {
        "Actual Rows",
        "Plan Rows",
        "rows",
        "rows_examined_per_scan",
        "rows_produced_per_join",
    }
    values: list[int] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in candidate_keys and isinstance(value, (int, float)):
                    values.append(int(value))
                else:
                    walk(value)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(plan)
    if not values:
        return None
    return max(values)


def _normalize_baseline_data(raw_baseline: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize baseline payloads from DB connectors and LLM providers."""
    if not isinstance(raw_baseline, dict):
        return {
            "plan": None,
            "estimated_cost": 0.0,
            "actual_time_ms": None,
        }

    if any(key in raw_baseline for key in ("plan", "estimated_cost", "actual_time_ms")):
        plan = raw_baseline.get("plan")
        return {
            "plan": plan,
            "estimated_cost": float(raw_baseline.get("estimated_cost", _estimate_cost_from_plan(plan)) or 0.0),
            "actual_time_ms": raw_baseline.get("actual_time_ms", _extract_actual_time_ms(plan)),
        }

    return {
        "plan": raw_baseline,
        "estimated_cost": _estimate_cost_from_plan(raw_baseline),
        "actual_time_ms": _extract_actual_time_ms(raw_baseline),
    }


def _build_result_signature(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a stable signature for baseline result comparisons."""
    sample_rows = rows[:20]
    checksum_source = json.dumps(sample_rows, sort_keys=True, default=str, ensure_ascii=False)
    checksum = hashlib.sha256(checksum_source.encode("utf-8")).hexdigest()
    column_names = list(sample_rows[0].keys()) if sample_rows else []
    return {
        "row_count": len(rows),
        "sample_size": len(sample_rows),
        "columns": column_names,
        "checksum": checksum,
    }


class RecognitionStage(Stage[None, RecognitionOutput]):
    """Recognition stage identifies performance baselines for SQL units."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
        config: SQLOptConfig | None = None,
        db_connector: Any | None = None,
        base_dir: str = "./runs",
    ) -> None:
        super().__init__("recognition", base_dir=base_dir)
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config
        self.db_connector = db_connector or getattr(self.llm_provider, "db_connector", None)

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RecognitionOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        self._progress_callback = progress_callback
        logger.info("=" * 60)
        logger.info("[RECOGNITION] Starting Recognition stage")
        logger.info(f"[RECOGNITION] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[RECOGNITION] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        parse_file = loader.get_parse_sql_units_with_branches_path()
        logger.info(f"[RECOGNITION] Parse file: {parse_file}")

        if not parse_file.exists():
            logger.warning(f"[RECOGNITION] Parse file not found: {parse_file}, using stub data")
            return self._create_stub_output()

        if parse_file.is_dir():
            units_dir = loader.get_parse_units_dir()
            index_file = units_dir / "_index.json"
            if index_file.exists():
                index_data = json.loads(index_file.read_text(encoding="utf-8"))
                unit_ids = index_data if isinstance(index_data, list) else index_data.get("unit_ids", [])
                all_branches = []
                for uid in unit_ids:
                    unit_file = units_dir / f"{uid}.json"
                    if unit_file.exists():
                        from sqlopt.contracts.parse import SQLUnitWithBranches

                        unit_data = json.loads(unit_file.read_text(encoding="utf-8"))
                        unit = SQLUnitWithBranches.from_json(json.dumps(unit_data))
                        all_branches.append(unit)
                parse_data = ParseOutput(sql_units_with_branches=all_branches)
                logger.info(
                    f"[RECOGNITION] Loaded {len(parse_data.sql_units_with_branches)} SQL unit(s) from per-unit files"
                )
            else:
                logger.warning("[RECOGNITION] Per-unit format detected but _index.json not found, using stub data")
                return self._create_stub_output()
        else:
            parse_data = ParseOutput.from_json(parse_file.read_text(encoding="utf-8"))
        logger.info(f"[RECOGNITION] Loaded {len(parse_data.sql_units_with_branches)} SQL unit(s) from parse stage")

        table_schemas: dict[str, TableSchema] | None = None
        table_schemas_file = loader.get_init_table_schemas_path()
        if table_schemas_file.exists():
            try:
                schemas_data = json.loads(table_schemas_file.read_text(encoding="utf-8"))
                table_schemas = {k: TableSchema(**v) for k, v in schemas_data.items()}
                logger.info(f"[RECOGNITION] Loaded {len(table_schemas)} table schema(s)")
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                logger.debug("[RECOGNITION] Failed to load table schemas, using heuristics")

        start_time = time.time()
        db_connector = self._get_db_connector()
        try:
            if self.config and self.config.concurrency.enabled and db_connector is None:
                logger.info("[RECOGNITION] Using concurrent execution mode")
                baselines = self._run_concurrent(parse_data, table_schemas, self._progress_callback)
            else:
                if db_connector is not None and self.config and self.config.concurrency.enabled:
                    logger.info("[RECOGNITION] DB baseline enabled, forcing sequential execution")
                baselines = self._run_sequential(parse_data, table_schemas, self._progress_callback, db_connector)
        finally:
            self._disconnect_db_connector()

        duration_seconds = time.time() - start_time
        logger.info(f"[RECOGNITION] Generated {len(baselines)} baseline(s)")
        output = RecognitionOutput(baselines=baselines, run_id=rid)
        file_stats = self._write_output(rid, output)
        self._write_summary(rid, output, duration_seconds, file_stats)
        logger.info("[RECOGNITION] Recognition stage completed")
        return output

    def _run_sequential(
        self,
        parse_data: ParseOutput,
        table_schemas: dict[str, TableSchema] | None,
        progress_callback: ProgressCallback | None,
        db_connector: Any | None,
    ) -> list[PerformanceBaseline]:
        baselines: list[PerformanceBaseline] = []
        platform = self._get_platform()
        total_branches = sum(len(su.branches) for su in parse_data.sql_units_with_branches)
        logger.info(f"[RECOGNITION] Processing {total_branches} branch(es) for baseline generation")

        done = 0
        for sql_unit in parse_data.sql_units_with_branches:
            for branch in sql_unit.branches:
                done += 1
                if progress_callback:
                    progress_callback(
                        f"Processing {sql_unit.sql_unit_id}.{branch.path_id}",
                        (done, total_branches),
                    )
                if not branch.is_valid:
                    logger.debug(f"[RECOGNITION]   Skipping invalid branch: {branch.path_id}")
                    continue
                baseline = self._create_baseline(
                    sql_unit_id=sql_unit.sql_unit_id,
                    path_id=branch.path_id,
                    expanded_sql=branch.expanded_sql,
                    branch_type=branch.branch_type,
                    table_schemas=table_schemas,
                    platform=platform,
                    db_connector=db_connector,
                )
                baselines.append(baseline)
                logger.info(
                    "[RECOGNITION]   [OK] %s.%s: cost=%s%s",
                    sql_unit.sql_unit_id,
                    branch.path_id,
                    baseline.estimated_cost,
                    f", error={baseline.execution_error}" if baseline.execution_error else "",
                )

        return baselines

    def _run_concurrent(
        self,
        parse_data: ParseOutput,
        table_schemas: dict[str, TableSchema] | None,
        progress_callback: ProgressCallback | None,
    ) -> list[PerformanceBaseline]:
        tasks: list[tuple[str, str, str, str | None]] = [
            (sql_unit.sql_unit_id, branch.path_id, branch.expanded_sql, branch.branch_type)
            for sql_unit in parse_data.sql_units_with_branches
            for branch in sql_unit.branches
            if branch.is_valid
        ]

        total = len(tasks)
        logger.info(f"[RECOGNITION] Processing {total} branch(es) concurrently")

        options = BatchOptions(
            max_workers=self.config.concurrency.max_workers if self.config else 4,
            max_concurrent=self.config.concurrency.llm_max_concurrent if self.config else 4,
            batch_size=self.config.concurrency.batch_size if self.config else 10,
            timeout_per_task=self.config.concurrency.timeout_per_task if self.config else 120,
            retry_count=self.config.concurrency.retry_count if self.config else 3,
            retry_delay=float(self.config.concurrency.retry_delay) if self.config else 1.0,
        )
        baselines: list[PerformanceBaseline] = []
        platform = self._get_platform()

        def process_task(task: tuple[str, str, str, str | None]) -> PerformanceBaseline:
            sql_unit_id, path_id, expanded_sql, branch_type = task
            return self._create_baseline(
                sql_unit_id=sql_unit_id,
                path_id=path_id,
                expanded_sql=expanded_sql,
                branch_type=branch_type,
                table_schemas=table_schemas,
                platform=platform,
                db_connector=None,
            )

        completed = [0]

        def on_progress(done: int, total_count: int) -> None:
            completed[0] = done
            logger.info(f"[RECOGNITION] Progress: {done}/{total_count}")
            if progress_callback:
                progress_callback(f"Processing {done}/{total_count}", (done, total_count))

        with ConcurrentExecutor(options) as executor:
            results: list[TaskResult] = executor.map(process_task, tasks, on_progress)

        for result in results:
            if result.success and result.result:
                baselines.append(result.result)
                logger.info(
                    "[RECOGNITION]   [OK] %s.%s: cost=%s%s",
                    result.result.sql_unit_id,
                    result.result.path_id,
                    result.result.estimated_cost,
                    f", error={result.result.execution_error}" if result.result.execution_error else "",
                )
            else:
                logger.warning("[RECOGNITION]   [FAIL] Failed: %s", result.error)

        return baselines

    def _create_stub_output(self) -> RecognitionOutput:
        baseline = PerformanceBaseline(
            sql_unit_id="stub-1",
            path_id="p1",
            original_sql="SELECT * FROM stub",
            plan={"cost": 100.0, "rows": 1000},
            estimated_cost=100.0,
            actual_time_ms=50.0,
        )
        return RecognitionOutput(baselines=[baseline])

    def _get_platform(self) -> str:
        return self.config.db_platform if self.config else "postgresql"

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
        except Exception:  # noqa: BLE001
            logger.debug("[RECOGNITION] Failed to disconnect DB connector", exc_info=True)

    def _generate_baseline_data(
        self,
        sql_for_execution: str,
        platform: str,
        db_connector: Any | None,
    ) -> dict[str, Any]:
        if db_connector is not None:
            return _normalize_baseline_data(db_connector.execute_explain(sql_for_execution))
        return _normalize_baseline_data(self.llm_provider.generate_baseline(sql_for_execution, platform))

    def _create_baseline(
        self,
        sql_unit_id: str,
        path_id: str,
        expanded_sql: str,
        branch_type: str | None,
        table_schemas: dict[str, TableSchema] | None,
        platform: str,
        db_connector: Any | None,
    ) -> PerformanceBaseline:
        if branch_type == "baseline_only":
            logger.info("[RECOGNITION]   [SKIP] Skipping EXPLAIN for baseline_only branch %s.%s", sql_unit_id, path_id)
            return PerformanceBaseline(
                sql_unit_id=sql_unit_id,
                path_id=path_id,
                original_sql=expanded_sql,
                plan=None,
                estimated_cost=0.0,
                actual_time_ms=None,
                branch_type="baseline_only",
            )

        sql_for_execution = _resolve_mybatis_params_for_explain(expanded_sql, table_schemas)
        logger.debug("[RECOGNITION]   EXPLAIN for %s.%s: %s...", sql_unit_id, path_id, sql_for_execution[:60])

        try:
            baseline_data = self._generate_baseline_data(sql_for_execution, platform, db_connector)
        except Exception as e:  # noqa: BLE001
            return PerformanceBaseline(
                sql_unit_id=sql_unit_id,
                path_id=path_id,
                original_sql=expanded_sql,
                plan=None,
                estimated_cost=0.0,
                actual_time_ms=None,
                execution_error=f"baseline_generation_failed: {e}",
                branch_type=branch_type,
            )

        plan = baseline_data.get("plan")
        actual_time_ms = baseline_data.get("actual_time_ms")
        rows_returned = None
        result_signature = None
        execution_error = None

        if db_connector is not None and _is_select_statement(sql_for_execution):
            try:
                query_started_at = time.perf_counter()
                rows = db_connector.execute_query(sql_for_execution)
                actual_time_ms = (time.perf_counter() - query_started_at) * 1000.0
                rows_returned = len(rows)
                result_signature = _build_result_signature(rows)
            except Exception as e:  # noqa: BLE001
                execution_error = f"query_execution_failed: {e}"

        return PerformanceBaseline(
            sql_unit_id=sql_unit_id,
            path_id=path_id,
            original_sql=expanded_sql,
            plan=plan,
            estimated_cost=float(baseline_data.get("estimated_cost", 0.0) or 0.0),
            actual_time_ms=actual_time_ms,
            rows_returned=rows_returned,
            rows_examined=_extract_rows_examined(plan),
            result_signature=result_signature,
            execution_error=execution_error,
            branch_type=branch_type,
        )

    def _write_output(self, run_id: str, output: RecognitionOutput) -> dict:
        """Write recognition output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/recognition/units/{unit_id}.json (per unit, grouped baselines)
        - runs/{run_id}/recognition/units/_index.json (unit ID list)
        - runs/{run_id}/recognition/baselines.json (backward compat)

        Returns:
            dict with 'unit_count', 'file_size_bytes' keys
        """
        output_dir = self.resolve_run_paths(run_id).recognition_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        file_manager = ContractFileManager(run_id, "recognition", base_dir=self.base_dir)

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
                    "original_sql": baseline.original_sql,
                    "plan": baseline.plan,
                    "estimated_cost": baseline.estimated_cost,
                    "actual_time_ms": baseline.actual_time_ms,
                    "rows_returned": baseline.rows_returned,
                    "rows_examined": baseline.rows_examined,
                    "result_signature": baseline.result_signature,
                    "execution_error": baseline.execution_error,
                    "branch_type": baseline.branch_type,
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
            content = generate_recognition_summary_markdown(
                output=output,
                duration_seconds=duration_seconds,
                file_size_bytes=file_stats["file_size_bytes"],
                files_count=file_stats["unit_count"] + 2,
            )
            output_dir = self.resolve_run_paths(run_id).recognition_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            summary_path = output_dir / "SUMMARY.md"
            summary_path.write_text(content, encoding="utf-8")
            logger.info(f"[RECOGNITION] Wrote SUMMARY.md ({len(content)} chars)")
        except Exception:  # noqa: BLE001
            logger.warning("[RECOGNITION] Failed to write SUMMARY.md, continuing")
