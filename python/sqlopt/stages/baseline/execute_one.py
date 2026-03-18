"""Baseline stage execute_one function.

Handles performance baseline collection for a single SQL unit through EXPLAIN.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from .baseline_collector import BaselineCollector, _substitute_bind_params


def _compute_result_hash(sql: str, params: dict, plan: dict) -> str:
    """Compute hash for result deduplication."""
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
    """Execute baseline collection for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration (must contain db.dsn)

    Returns:
        Baseline result dictionary
    """
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

    # Use BaselineCollector to collect performance data
    collector = BaselineCollector(config)
    result = collector.collect(sql_unit)

    # Build execution plan summary
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
        # Extended metrics
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

    # Validate against contract
    validator.validate("baseline_result", baseline_result)

    # Append to baseline results
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


class BaselineStage:
    """Baseline stage wrapper for V8 architecture."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.collector = BaselineCollector(self.config)

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Execute baseline collection for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Baseline result dictionary
        """
        return execute_one(sql_unit, run_dir, validator, self.config)
