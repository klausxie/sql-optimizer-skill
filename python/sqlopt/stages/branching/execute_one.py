"""Branching stage execute_one function.

Handles branch generation from MyBatis dynamic SQL templates.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...manifest import log_event
from ...run_paths import canonical_paths
from .brancher import Brancher, generate_branches


@dataclass
class BranchingResult:
    """Result of branching for a single SQL unit."""

    sql_key: str
    branches: list[dict[str, Any]]
    branch_count: int
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
    """Execute branching for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary with sql_key and sql fields
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Branching result dictionary
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

    # Get branching configuration
    strategy = config.get("branching_strategy", "all_combinations")
    max_branches = config.get("max_branches", 100)

    # Run branch generation
    brancher = Brancher(strategy=strategy, max_branches=max_branches)
    start_time = datetime.now(timezone.utc)

    # Extract conditions from sql_unit if present
    conditions = sql_unit.get("conditions", [])

    # Generate branches using the Brancher
    branch_objects = brancher.generate(sql, conditions)
    branches = [
        {
            "branch_id": b.branch_id,
            "active_conditions": b.active_conditions,
            "sql": b.sql,
            "condition_count": b.condition_count,
            "risk_flags": b.risk_flags,
        }
        for b in branch_objects
    ]

    end_time = datetime.now(timezone.utc)
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    branching_result = {
        "sqlKey": sql_key,
        "branches": branches,
        "branchCount": len(branches),
        "executionTimeMs": execution_time_ms,
        "trace": {
            "stage": "branching",
            "sql_key": sql_key,
            "executor": "brancher",
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    log_event(
        paths.manifest_path,
        "branching",
        "done",
        {"statement_key": sql_key, "branch_count": len(branches)},
    )

    return branching_result


class BranchingStage:
    """Branching stage wrapper for V8 architecture."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.brancher = Brancher(
            strategy=self.config.get("branching_strategy", "all_combinations"),
            max_branches=self.config.get("max_branches", 100),
        )

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Execute branching for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Branching result dictionary
        """
        return execute_one(sql_unit, run_dir, validator, self.config)
