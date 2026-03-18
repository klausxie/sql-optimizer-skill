"""Optimize stage execute_one function.

Handles optimization proposal generation for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl, write_json
from ...manifest import log_event
from ...run_paths import canonical_paths


@dataclass
class OptimizationProposal:
    sql_key: str
    original_sql: str
    candidates: list[dict[str, Any]]
    trace: dict[str, Any]


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute optimization for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Optimization proposal dictionary
    """
    config = config or {}
    paths = canonical_paths(run_dir)

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )
    original_sql = sql_unit.get("sql", "")

    proposal = {
        "sqlKey": sql_key,
        "originalSql": original_sql,
        "namespace": sql_unit.get("namespace", ""),
        "statementId": sql_unit.get("statementId", ""),
        "candidates": [],
        "trace": {
            "stage": "optimize",
            "sql_key": sql_key,
            "executor": "rule_engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    validator.validate("optimization_proposal", proposal)
    append_jsonl(paths.proposals_path, proposal)

    log_event(
        paths.manifest_path,
        "optimize",
        "done",
        {"statement_key": sql_key},
    )

    return proposal
