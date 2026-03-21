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
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .baseline_collector import BaselineCollector


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
    sql_key = str(sql_unit.get("sqlKey") or "unknown")
    sql = str(sql_unit.get("sql") or "")
    params = sql_unit.get("paramExample", {}) or {}

    validator.validate_stage_input("recognition", sql_unit)
    collector = BaselineCollector(config)
    result = collector.collect(sql_unit)

    baseline_result = {
        "sql_key": result.sql_key,
        "execution_time_ms": result.execution_time_ms,
        "rows_scanned": result.rows_examined,
        "execution_plan": {
            "node_type": result.explain_plan.get("scan_type", "UNKNOWN"),
            "index_used": result.index_used,
            "cost": result.explain_plan.get("estimated_cost"),
        },
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
    dependencies: list[str] = ["branching", "pruning"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        sql_units: list[dict[str, Any]]
        if paths.branches_path.exists():
            sql_units = [
                row for row in read_jsonl(paths.branches_path) if isinstance(row, dict)
            ]
        elif paths.scan_units_path.exists():
            raw = json.loads(paths.scan_units_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raw = []
            sql_units = [row for row in raw if isinstance(row, dict)]
        else:
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[
                    f"input file not found: {paths.branches_path} or {paths.scan_units_path}"
                ],
                warnings=[],
            )
        baseline_results: list[dict[str, Any]] = []
        for sql_unit in sql_units:
            try:
                baseline_result = execute_one(sql_unit, run_dir, validator, self.config)
                baseline_results.append(baseline_result)
            except Exception as exc:
                errors.append(
                    f"error processing {sql_unit.get('sqlKey', 'unknown')}: {exc}"
                )

        if baseline_results:
            write_jsonl(paths.baseline_results_path, baseline_results)
        else:
            write_jsonl(paths.baseline_results_path, [])

        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.baseline_results_path],
            artifacts={
                "baseline_results": baseline_results,
                "baseline_count": len(baseline_results),
                "error_count": len(errors),
            },
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
