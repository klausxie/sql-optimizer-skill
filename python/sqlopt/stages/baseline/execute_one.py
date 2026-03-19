"""Baseline stage execute_one function.

Handles performance baseline collection for a single SQL unit through EXPLAIN.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .baseline_collector import BaselineCollector, _substitute_bind_params


def _compute_result_hash(sql: str, params: dict, plan: dict) -> str:
    content = json.dumps(
        {"sql": sql, "params": params, "plan": plan}, sort_keys=True, default=str
    )
    return hashlib.md5(content.encode()).hexdigest()[:12]


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    paths = canonical_paths(run_dir)

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )
    sql = sql_unit.get("sql", "")
    params = sql_unit.get("paramExample", {})

    collector = BaselineCollector(config)
    result = collector.collect(sql_unit)

    execution_plan = {
        "node_type": result.explain_plan.get("scan_type", "UNKNOWN"),
        "index_used": result.index_used,
        "cost": result.explain_plan.get("estimated_cost"),
    }

    baseline_result = {
        "sql_key": result.sql_key,
        "execution_time_ms": result.execution_time_ms,
        "rows_scanned": result.rows_examined,
        "execution_plan": execution_plan,
        "result_hash": _compute_result_hash(sql, params, result.explain_plan),
        "rows_returned": result.rows_returned,
        "database_platform": result.database_platform,
        "sample_params": result.sample_params,
        "actual_execution_time_ms": result.actual_execution_time_ms,
        "buffer_hit_count": result.buffer_hit_count,
        "buffer_read_count": result.buffer_read_count,
        "explain_plan": result.explain_plan,
        "trace": {
            "stage": "baseline",
            "sql_key": sql_key,
            "executor": "baseline_collector",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    validator.validate("baseline_result", baseline_result)
    append_jsonl(paths.baseline_results_path, baseline_result)

    log_event(
        paths.manifest_path,
        "baseline",
        "done",
        {
            "statement_key": sql_key,
            "execution_time_ms": result.execution_time_ms,
            "rows_scanned": result.rows_examined,
        },
    )

    return baseline_result


@stage_registry.register
class BaselineStage(Stage):
    name: str = "baseline"
    version: str = "1.0.0"
    dependencies: list[str] = ["discovery"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.collector = BaselineCollector(self.config)

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        validator.validate_stage_input("baseline", {})

        collector = BaselineCollector(self.config)

        sql_units: list[dict[str, Any]] = []
        if paths.scan_units_path.exists():
            try:
                with open(paths.scan_units_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            record = json.loads(line)
                            if "sqlUnits" in record:
                                sql_units.extend(record["sqlUnits"])
            except Exception as e:
                errors.append(f"failed to load SQL units: {e}")

        baseline_results: list[dict[str, Any]] = []

        for sql_unit in sql_units:
            try:
                result = collector.collect(sql_unit)

                sql_key = sql_unit.get(
                    "sqlKey",
                    sql_unit.get("namespace", "unknown")
                    + "."
                    + sql_unit.get("statementId", "unknown"),
                )
                sql = sql_unit.get("sql", "")
                params = sql_unit.get("paramExample", {})

                execution_plan = {
                    "node_type": result.explain_plan.get("scan_type", "UNKNOWN"),
                    "index_used": result.index_used,
                    "cost": result.explain_plan.get("estimated_cost"),
                }

                baseline_result = {
                    "sql_key": result.sql_key,
                    "execution_time_ms": result.execution_time_ms,
                    "rows_scanned": result.rows_examined,
                    "execution_plan": execution_plan,
                    "result_hash": _compute_result_hash(
                        sql, params, result.explain_plan
                    ),
                    "rows_returned": result.rows_returned,
                    "database_platform": result.database_platform,
                    "sample_params": result.sample_params,
                    "actual_execution_time_ms": result.actual_execution_time_ms,
                    "buffer_hit_count": result.buffer_hit_count,
                    "buffer_read_count": result.buffer_read_count,
                    "explain_plan": result.explain_plan,
                    "trace": {
                        "stage": "baseline",
                        "sql_key": sql_key,
                        "executor": "baseline_collector",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }

                validator.validate("baseline_result", baseline_result)
                append_jsonl(paths.baseline_results_path, baseline_result)
                baseline_results.append(baseline_result)

                log_event(
                    paths.manifest_path,
                    "baseline",
                    "done",
                    {
                        "statement_key": sql_key,
                        "execution_time_ms": result.execution_time_ms,
                        "rows_scanned": result.rows_examined,
                    },
                )

            except Exception as e:
                errors.append(f"error processing SQL unit: {e}")

        if baseline_results:
            try:
                validator.validate_stage_output("baseline", baseline_results[0])
            except Exception as e:
                errors.append(f"output validation error: {e}")

        artifacts = {
            "baseline_results": baseline_results,
            "total_count": len(baseline_results),
        }

        if paths.baseline_results_path.exists():
            output_files.append(paths.baseline_results_path)

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts=artifacts,
            errors=errors,
            warnings=warnings,
        )

    def get_input_contracts(self) -> list[str]:
        return ["sqlunit"]

    def get_output_contracts(self) -> list[str]:
        return ["baseline_result"]

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        return execute_one(sql_unit, run_dir, validator, self.config)
