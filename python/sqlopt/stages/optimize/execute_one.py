"""Optimize stage execute_one function.

Handles optimization proposal generation for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from ...platforms.sql.optimizer_sql import generate_proposal


def _load_sql_units(run_dir: Path) -> dict[str, dict[str, Any]]:
    paths = canonical_paths(run_dir)
    input_path = paths.branches_path if paths.branches_path.exists() else paths.scan_units_path
    rows = [row for row in read_jsonl(input_path) if isinstance(row, dict)] if input_path.exists() else []
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        sql_key = str(row.get("sqlKey") or "").strip()
        if sql_key:
            result[sql_key] = row
    return result


def _fallback_proposal(sql_key: str, error: Exception) -> dict[str, Any]:
    return {
        "sqlKey": sql_key,
        "issues": [{"code": "OPTIMIZE_GENERATION_FAILED", "detail": str(error)}],
        "dbEvidenceSummary": {},
        "planSummary": {},
        "suggestions": [],
        "verdict": "NO_ACTION",
        "confidence": "low",
        "estimatedBenefit": "unknown",
    }


def execute_one(
    baseline_result: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    paths = canonical_paths(run_dir)
    sql_key = str(baseline_result.get("sql_key") or "unknown")
    validator.validate_stage_input("optimize", baseline_result)

    sql_unit = _load_sql_units(run_dir).get(sql_key)
    if sql_unit is None:
        sql_unit = {
            "sqlKey": sql_key,
            "sql": "",
            "statementType": "SELECT",
            "riskFlags": [],
        }

    try:
        proposal = generate_proposal(sql_unit, config)
    except Exception as exc:
        proposal = _fallback_proposal(sql_key, exc)

    validator.validate("optimization_proposal", proposal)
    log_event(paths.manifest_path, "optimize", "done", {"statement_key": sql_key})
    return proposal


@stage_registry.register
class OptimizeStage(Stage):
    """Optimize stage implementation for V8 architecture."""

    name: str = "optimize"
    version: str = "1.0.0"
    dependencies: list[str] = ["baseline"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        if not paths.baseline_results_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {paths.baseline_results_path}"],
                warnings=[],
            )

        baseline_results = [
            row for row in read_jsonl(paths.baseline_results_path) if isinstance(row, dict)
        ]
        proposals: list[dict[str, Any]] = []
        for baseline_result in baseline_results:
            try:
                proposals.append(execute_one(baseline_result, run_dir, validator, self.config))
            except Exception as exc:
                errors.append(
                    f"error processing {baseline_result.get('sql_key', 'unknown')}: {exc}"
                )

        write_jsonl(paths.proposals_path, proposals)
        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.proposals_path],
            artifacts={
                "proposals": proposals,
                "proposal_count": len(proposals),
                "actionable_count": sum(
                    1 for row in proposals if str(row.get("verdict") or "").upper() == "ACTIONABLE"
                ),
            },
            errors=errors,
            warnings=warnings,
        )

    def get_input_contracts(self) -> list[str]:
        return ["baseline_result"]

    def get_output_contracts(self) -> list[str]:
        return ["optimization_proposal"]

    def execute_one(
        self,
        baseline_result: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        return execute_one(baseline_result, run_dir, validator, self.config)


@dataclass
class OptimizationProposal:
    """Optimization proposal for a single SQL unit."""

    sql_key: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
