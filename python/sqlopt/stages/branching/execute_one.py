"""Branching stage execute_one function.

Handles branch generation from MyBatis dynamic SQL templates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import StageRegistry, stage_registry
from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .brancher import Brancher


@stage_registry.register
class BranchingStage(Stage):
    """Branching stage implementation for V8 architecture.

    Generates executable SQL branches from MyBatis dynamic SQL templates.
    """

    name: str = "branching"
    version: str = "1.0.0"
    dependencies: list[str] = ["discovery"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.brancher = Brancher(
            strategy=self.config.get("branching_strategy", "all_combinations"),
            max_branches=self.config.get("max_branches", 100),
        )

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        sqlunits_path = paths.scan_units_path
        if not sqlunits_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {sqlunits_path}"],
                warnings=[],
            )

        all_branches: list[dict[str, Any]] = []

        try:
            with open(sqlunits_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    import json

                    record = json.loads(line)
                    sql_units = record.get("sqlUnits", [])
                    for unit in sql_units:
                        try:
                            validator.validate_stage_input("branching", unit)
                        except Exception as e:
                            errors.append(f"input validation error: {e}")
                            continue

                        result = _execute_one(
                            unit,
                            run_dir,
                            validator,
                            self.config,
                            self.brancher,
                        )

                        all_branches.append(result)

        except Exception as e:
            errors.append(f"error reading sqlunits: {e}")

        branching_result = {
            "branches": all_branches,
            "totalBranchCount": len(all_branches),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for branch_result in all_branches:
            try:
                validator.validate_stage_output("branching", branch_result)
            except Exception as e:
                errors.append(f"output validation error: {e}")

        append_jsonl(paths.branches_path, branching_result)
        output_files.append(paths.branches_path)

        log_event(
            paths.manifest_path,
            "branching",
            "done",
            {
                "run_id": context.run_id,
                "branch_count": len(all_branches),
            },
        )

        artifacts = {
            "branches": all_branches,
            "total_branch_count": len(all_branches),
        }

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
        return ["sqlunit"]

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        return _execute_one(sql_unit, run_dir, validator, self.config, self.brancher)


def _execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
    brancher: Brancher | None = None,
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

    strategy = config.get("branching_strategy", "all_combinations")
    max_branches = config.get("max_branches", 100)

    if brancher is None:
        brancher = Brancher(strategy=strategy, max_branches=max_branches)

    start_time = datetime.now(timezone.utc)

    conditions = sql_unit.get("conditions", [])

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


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _execute_one(sql_unit, run_dir, validator, config)
