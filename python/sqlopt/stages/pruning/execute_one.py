"""Pruning stage execute_one function.

Handles risk detection and branch pruning for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .analyzer import RiskDetector


@stage_registry.register
class PruningStage(Stage):
    """Pruning stage implementation for V8 architecture."""

    name: str = "pruning"
    version: str = "1.0.0"
    dependencies: list[str] = ["branching"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.detector = RiskDetector()

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        input_path = paths.branches_path if paths.branches_path.exists() else paths.scan_units_path
        if not input_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {input_path}"],
                warnings=[],
            )

        sql_units = [row for row in read_jsonl(input_path) if isinstance(row, dict)]
        risk_records: list[dict[str, Any]] = []
        for unit in sql_units:
            try:
                validator.validate_stage_input("pruning", unit)
                risk_records.append(self._prune_unit(unit, run_dir, validator))
            except Exception as exc:
                errors.append(
                    f"error processing {unit.get('sqlKey', 'unknown')}: {exc}"
                )

        write_jsonl(paths.pruning_risks_path, risk_records)
        log_event(
            paths.manifest_path,
            "pruning",
            "done",
            {
                "run_id": context.run_id,
                "sql_units_processed": len(risk_records),
                "risk_count": sum(len(row.get("risks", [])) for row in risk_records),
            },
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.pruning_risks_path],
            artifacts={
                "risks": risk_records,
                "sql_unit_count": len(risk_records),
                "risk_count": sum(len(row.get("risks", [])) for row in risk_records),
            },
            errors=errors,
            warnings=warnings,
        )

    def _prune_unit(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        return execute_one(sql_unit, run_dir, validator, self.config)

    def get_input_contracts(self) -> list[str]:
        return ["sqlunit"]

    def get_output_contracts(self) -> list[str]:
        return []

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        return self._prune_unit(sql_unit, run_dir, validator)


@dataclass
class PruningResult:
    """Result of pruning analysis for a single SQL unit."""

    sql_key: str
    risks: list[dict[str, Any]]
    pruned_branches: list[int]
    execution_time_ms: float
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = config or {}
    paths = canonical_paths(run_dir)
    sql_key = str(sql_unit.get("sqlKey") or "unknown")
    detector = RiskDetector()
    start_time = datetime.now(timezone.utc)
    risks = detector.analyze(str(sql_unit.get("sql") or ""), sql_key)
    execution_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    branch_ids = {
        int(branch.get("id"))
        for branch in (sql_unit.get("branches") or [])
        if isinstance(branch, dict) and branch.get("id") is not None
    }
    pruned_branches = sorted(branch_ids) if any(r.severity == "HIGH" for r in risks) else []

    result = {
        "sqlKey": sql_key,
        "risks": [
            {
                "riskType": risk.risk_type,
                "severity": risk.severity,
                "message": risk.suggestion,
                "branchIds": pruned_branches,
            }
            for risk in risks
        ],
        "prunedBranches": pruned_branches,
        "recommendedForBaseline": bool(risks),
        "trace": {
            "stage": "pruning",
            "sql_key": sql_key,
            "executor": "risk_detector",
            "executionTimeMs": execution_time_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    log_event(
        paths.manifest_path,
        "pruning",
        "done",
        {"statement_key": sql_key, "risk_count": len(risks)},
    )
    return result
