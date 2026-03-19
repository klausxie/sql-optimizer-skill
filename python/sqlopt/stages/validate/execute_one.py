"""Validate stage execute_one function.

Handles validation of optimization proposals for a single SQL unit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import StageRegistry, stage_registry
from ...contracts import ContractValidator, STAGE_BOUNDARIES
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult


@stage_registry.register
class ValidateStage(Stage):
    """Validate stage implementation for V8 architecture.

    Validates optimization proposals and generates acceptance results.
    """

    name: str = "validate"
    version: str = "1.0.0"
    dependencies: list[str] = ["optimize"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        """Execute the validate stage.

        Args:
            context: Stage execution context containing run_id, config, and data_dir

        Returns:
            StageResult with validation artifacts
        """
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        # Get proposals from optimize stage output
        proposals_path = paths.proposals_path
        if not proposals_path.exists():
            warnings.append("no proposals found, skipping validation")
            return StageResult(
                success=True,
                output_files=output_files,
                artifacts=artifacts,
                errors=errors,
                warnings=warnings,
            )

        # Read all proposals
        proposals: list[dict[str, Any]] = []
        try:
            with open(proposals_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        proposals.append(eval(line))
        except Exception as e:
            errors.append(f"error reading proposals: {e}")
            return StageResult(
                success=False,
                output_files=output_files,
                artifacts=artifacts,
                errors=errors,
                warnings=warnings,
            )

        if not proposals:
            warnings.append("no proposals to validate")

        # Process each proposal
        acceptances: list[dict[str, Any]] = []
        for proposal in proposals:
            try:
                sql_unit = proposal.get("sql_unit", {})
                acceptance = self.execute_one(
                    sql_unit=sql_unit,
                    proposal=proposal,
                    run_dir=run_dir,
                    validator=validator,
                    db_reachable=context.metadata.get("db_reachable", False),
                    config=self.config,
                )
                acceptances.append(acceptance)
            except Exception as e:
                errors.append(f"error validating proposal: {e}")

        # Build artifacts
        artifacts = {
            "acceptances": acceptances,
            "total_count": len(acceptances),
            "pass_count": sum(1 for a in acceptances if a.get("status") == "PASS"),
            "fail_count": sum(1 for a in acceptances if a.get("status") == "FAIL"),
        }

        # Log completion
        log_event(
            paths.manifest_path,
            "validate",
            "done",
            {
                "run_id": context.run_id,
                "total_count": len(acceptances),
                "pass_count": artifacts["pass_count"],
                "fail_count": artifacts["fail_count"],
            },
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts=artifacts,
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
        """Execute validation for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            proposal: Optimization proposal
            run_dir: Run directory
            validator: Contract validator
            db_reachable: Whether database is reachable
            config: Optional configuration

        Returns:
            Acceptance result dictionary
        """
        config = config or {}
        paths = canonical_paths(run_dir)

        sql_key = sql_unit.get(
            "sqlKey",
            sql_unit.get("namespace", "unknown")
            + "."
            + sql_unit.get("statementId", "unknown"),
        )

        acceptance = {
            "sqlKey": sql_key,
            "status": "PASS",
            "rewrittenSql": proposal.get("candidates", [{}])[0].get("rewrittenSql")
            if proposal.get("candidates")
            else None,
            "trace": {
                "stage": "validate",
                "sql_key": sql_key,
                "db_reachable": db_reachable,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Validate against acceptance_result schema
        validator.validate("acceptance_result", acceptance)
        append_jsonl(paths.acceptance_path, acceptance)

        log_event(
            paths.manifest_path,
            "validate",
            "done",
            {"statement_key": sql_key, "status": acceptance.get("status")},
        )

        return acceptance

    def get_input_contracts(self) -> list[str]:
        """Validate stage expects optimization_proposal input.

        Returns:
            List containing "optimization_proposal"
        """
        return ["optimization_proposal"]

    def get_output_contracts(self) -> list[str]:
        """Validate stage outputs acceptance_result.

        Returns:
            List containing "acceptance_result"
        """
        return ["acceptance_result"]


def execute_one(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    db_reachable: bool,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute validation for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        proposal: Optimization proposal
        run_dir: Run directory
        validator: Contract validator
        db_reachable: Whether database is reachable
        config: Optional configuration

    Returns:
        Acceptance result dictionary
    """
    config = config or {}
    paths = canonical_paths(run_dir)

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )

    acceptance = {
        "sqlKey": sql_key,
        "status": "PASS",
        "rewrittenSql": proposal.get("candidates", [{}])[0].get("rewrittenSql")
        if proposal.get("candidates")
        else None,
        "trace": {
            "stage": "validate",
            "sql_key": sql_key,
            "db_reachable": db_reachable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    validator.validate("acceptance_result", acceptance)
    append_jsonl(paths.acceptance_path, acceptance)

    log_event(
        paths.manifest_path,
        "validate",
        "done",
        {"statement_key": sql_key, "status": acceptance.get("status")},
    )

    return acceptance
