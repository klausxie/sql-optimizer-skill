"""Validate stage execute_one function.

Handles validation of optimization proposals for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from ...platforms.sql.validator_sql import validate_proposal


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


@stage_registry.register
class ValidateStage(Stage):
    """Validate stage implementation for V8 architecture."""

    name: str = "validate"
    version: str = "1.0.0"
    dependencies: list[str] = ["optimize"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        if not paths.proposals_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {paths.proposals_path}"],
                warnings=[],
            )

        proposals = [row for row in read_jsonl(paths.proposals_path) if isinstance(row, dict)]
        sql_units = _load_sql_units(run_dir)
        acceptances: list[dict[str, Any]] = []
        db_reachable = bool(context.metadata.get("db_reachable", False))

        for proposal in proposals:
            try:
                validator.validate_stage_input("validate", proposal)
                sql_key = str(proposal.get("sqlKey") or "unknown")
                sql_unit = sql_units.get(sql_key)
                if sql_unit is None:
                    raise ValueError(f"sql unit not found for proposal: {sql_key}")
                acceptance = self.execute_one(
                    sql_unit=sql_unit,
                    proposal=proposal,
                    run_dir=run_dir,
                    validator=validator,
                    db_reachable=db_reachable,
                    config=self.config,
                )
                validator.validate_stage_output("validate", acceptance)
                acceptances.append(acceptance)
            except Exception as exc:
                errors.append(f"error validating proposal: {exc}")

        write_jsonl(paths.acceptance_path, acceptances)
        log_event(
            paths.manifest_path,
            "validate",
            "done",
            {
                "run_id": context.run_id,
                "total_count": len(acceptances),
                "pass_count": sum(1 for a in acceptances if a.get("status") == "PASS"),
                "fail_count": sum(1 for a in acceptances if a.get("status") == "FAIL"),
            },
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.acceptance_path],
            artifacts={
                "acceptances": acceptances,
                "total_count": len(acceptances),
                "pass_count": sum(1 for a in acceptances if a.get("status") == "PASS"),
                "fail_count": sum(1 for a in acceptances if a.get("status") == "FAIL"),
            },
            errors=errors,
            warnings=warnings,
        )

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        proposal: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
        db_reachable: bool,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return execute_one(sql_unit, proposal, run_dir, validator, db_reachable, config)

    def get_input_contracts(self) -> list[str]:
        return ["optimization_proposal"]

    def get_output_contracts(self) -> list[str]:
        return ["acceptance_result"]


@dataclass
class ValidationExecutionTrace:
    sql_key: str
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    db_reachable: bool,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = canonical_paths(run_dir)
    result = validate_proposal(
        sql_unit,
        proposal,
        db_reachable,
        config=config or {},
        evidence_dir=canonical_paths(run_dir).sql_evidence_dir(str(sql_unit.get("sqlKey") or "unknown")),
        fragment_catalog={},
    )
    acceptance = result.to_contract() if hasattr(result, "to_contract") else dict(result)
    validator.validate("acceptance_result", acceptance)
    log_event(
        canonical_paths(run_dir).manifest_path,
        "validate",
        "done",
        {"statement_key": acceptance.get("sqlKey"), "status": acceptance.get("status")},
    )
    return acceptance
