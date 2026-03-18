"""Pruning stage execute_one function.

Handles risk detection and branch pruning for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from .analyzer import RiskDetector


@dataclass
class PruningResult:
    """Result of pruning analysis for a single SQL unit."""

    sql_key: str
    risks: list[dict[str, Any]]
    pruned_branches: list[str]
    execution_time_ms: float
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute pruning analysis for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Pruning result dictionary
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

    # Run risk detection
    detector = RiskDetector()
    start_time = datetime.now(timezone.utc)
    risks = detector.analyze(original_sql, sql_key)
    end_time = datetime.now(timezone.utc)

    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    # Determine pruned branches based on risk severity
    pruned_branches = []
    for risk in risks:
        if risk.severity == "HIGH":
            # High severity risks indicate branches that should be pruned
            pruned_branches.append(f"risk:{risk.risk_type}")

    pruning_result = {
        "sqlKey": sql_key,
        "risks": [risk.to_dict() for risk in risks],
        "prunedBranches": pruned_branches,
        "executionTimeMs": execution_time_ms,
        "trace": {
            "stage": "pruning",
            "sql_key": sql_key,
            "executor": "risk_detector",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    log_event(
        paths.manifest_path,
        "pruning",
        "done",
        {"statement_key": sql_key, "risk_count": len(risks)},
    )

    return pruning_result


class PruningStage:
    """Pruning stage wrapper for V8 architecture."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.detector = RiskDetector()

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Execute pruning for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Pruning result dictionary
        """
        return execute_one(sql_unit, run_dir, validator, self.config)
