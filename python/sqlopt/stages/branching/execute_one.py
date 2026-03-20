"""Branching stage execute_one function.

Handles branch generation from MyBatis dynamic SQL templates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .brancher import Brancher


@stage_registry.register
class BranchingStage(Stage):
    """Branching stage implementation for V8 architecture."""

    name: str = "branching"
    version: str = "1.0.0"
    dependencies: list[str] = ["discovery"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.brancher = Brancher(
            strategy=self.config.get("branching", {}).get(
                "strategy", self.config.get("branching_strategy", "all_combinations")
            ),
            max_branches=self.config.get("branching", {}).get(
                "max_branches", self.config.get("max_branches", 100)
            ),
        )

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        if not paths.scan_units_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {paths.scan_units_path}"],
                warnings=[],
            )

        all_units = [row for row in read_jsonl(paths.scan_units_path) if isinstance(row, dict)]
        branched_units: list[dict[str, Any]] = []
        total_branch_count = 0

        for unit in all_units:
            try:
                validator.validate_stage_input("branching", unit)
                result = _execute_one(unit, run_dir, validator, self.config, self.brancher)
                validator.validate_stage_output("branching", result)
                branched_units.append(result)
                total_branch_count += int(result.get("branchCount") or 0)
            except Exception as exc:
                errors.append(
                    f"error processing {unit.get('sqlKey', 'unknown')}: {exc}"
                )

        write_jsonl(paths.branches_path, branched_units)
        log_event(
            paths.manifest_path,
            "branching",
            "done",
            {"run_id": context.run_id, "branch_count": total_branch_count},
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.branches_path],
            artifacts={
                "sql_units": branched_units,
                "sql_unit_count": len(branched_units),
                "total_branch_count": total_branch_count,
            },
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
    sql_key = str(sql_unit.get("sqlKey") or "unknown")
    sql = str(sql_unit.get("templateSql") or sql_unit.get("sql") or "")
    conditions = sql_unit.get("conditions", [])

    strategy = config.get("branching", {}).get(
        "strategy", config.get("branching_strategy", "all_combinations")
    )
    max_branches = config.get("branching", {}).get(
        "max_branches", config.get("max_branches", 100)
    )
    if brancher is None:
        brancher = Brancher(strategy=strategy, max_branches=max_branches)

    start_time = datetime.now(timezone.utc)
    branch_objects = brancher.generate(sql, conditions)
    execution_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    risk_flags = list(dict.fromkeys(str(x) for x in (sql_unit.get("riskFlags") or [])))
    branches: list[dict[str, Any]] = []
    for idx, branch in enumerate(branch_objects, start=1):
        branches.append(
            {
                "id": idx,
                "conditions": list(branch.active_conditions),
                "sql": branch.sql,
                "type": "conditional" if branch.condition_count else "static",
            }
        )
        for flag in branch.risk_flags:
            text = str(flag).strip()
            if text and text not in risk_flags:
                risk_flags.append(text)

    enriched_unit = dict(sql_unit)
    enriched_unit["branches"] = branches
    enriched_unit["branchCount"] = len(branches)
    enriched_unit["problemBranchCount"] = sum(1 for b in branch_objects if b.risk_flags)
    enriched_unit["riskFlags"] = risk_flags
    enriched_unit["trace"] = {
        "stage": "branching",
        "sql_key": sql_key,
        "executor": "brancher",
        "strategy": strategy,
        "executionTimeMs": execution_time_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log_event(
        paths.manifest_path,
        "branching",
        "done",
        {"statement_key": sql_key, "branch_count": len(branches)},
    )
    return enriched_unit


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _execute_one(sql_unit, run_dir, validator, config)
