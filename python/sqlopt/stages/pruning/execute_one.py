"""Pruning stage execute_one function.

Handles risk detection and branch pruning for a single SQL unit.
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
from .analyzer import RiskDetector


@stage_registry.register
class PruningStage(Stage):
    """Pruning stage implementation for V8 architecture.

    Performs risk detection and branch pruning for SQL units.
    """

    name: str = "pruning"
    version: str = "1.0.0"
    dependencies: list[str] = ["discovery", "branching"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.detector = RiskDetector()

    def execute(self, context: StageContext) -> StageResult:
        """Execute the pruning stage.

        Args:
            context: Stage execution context containing run_id, config, and data_dir

        Returns:
            StageResult with pruning artifacts
        """
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        # Get SQL units from input (produced by branching stage)
        scan_units_path = paths.scan_units_path
        if not scan_units_path.exists():
            errors.append(
                "no scan units found - ensure discovery and branching stages completed"
            )
            return StageResult(
                success=False,
                output_files=output_files,
                artifacts=artifacts,
                errors=errors,
                warnings=warnings,
            )

        # Read and process each SQL unit
        all_risks: list[dict[str, Any]] = []
        sql_units_processed = 0

        try:
            with scan_units_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    import json

                    record = json.loads(line)
                    sql_units = record.get("sqlUnits", [])
                    if not sql_units:
                        # Handle single sqlunit format
                        if "sqlKey" in record:
                            sql_units = [record]
                        else:
                            continue

                    for unit in sql_units:
                        try:
                            result = self._prune_unit(unit, run_dir, validator)
                            all_risks.append(result)
                            sql_units_processed += 1
                        except Exception as e:
                            errors.append(
                                f"error processing {unit.get('sqlKey', 'unknown')}: {e}"
                            )

        except Exception as e:
            errors.append(f"error reading scan units: {e}")

        # Build pruning result
        pruning_result = {
            "sqlUnitsProcessed": sql_units_processed,
            "totalRisks": len(all_risks),
            "risks": all_risks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to branching results (pruning modifies branch metadata)
        output_files.append(paths.branches_path)

        # Log completion
        log_event(
            paths.manifest_path,
            "pruning",
            "done",
            {
                "run_id": context.run_id,
                "sql_units_processed": sql_units_processed,
                "risk_count": len(all_risks),
            },
        )

        # Build artifacts
        artifacts = {
            "risks": all_risks,
            "sql_units_processed": sql_units_processed,
            "total_risk_count": len(all_risks),
        }

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts=artifacts,
            errors=errors,
            warnings=warnings,
        )

    def _prune_unit(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Prune risks for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Pruning result dictionary
        """
        paths = canonical_paths(run_dir)

        sql_key = sql_unit.get(
            "sqlKey",
            sql_unit.get("namespace", "unknown")
            + "."
            + sql_unit.get("statementId", "unknown"),
        )
        original_sql = sql_unit.get("sql", "")

        # Run risk detection
        start_time = datetime.now(timezone.utc)
        risks = self.detector.analyze(original_sql, sql_key)
        end_time = datetime.now(timezone.utc)

        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        # Determine pruned branches based on risk severity
        pruned_branches = []
        for risk in risks:
            if risk.severity == "HIGH":
                pruned_branches.append(f"risk:{risk.risk_type}")

        result = {
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

        return result

    def get_input_contracts(self) -> list[str]:
        """Pruning takes sqlunit as input.

        Returns:
            List containing "sqlunit"
        """
        return ["sqlunit"]

    def get_output_contracts(self) -> list[str]:
        """Pruning produces custom risks output (not a standard schema).

        Returns:
            Empty list since output is not a known schema
        """
        return []

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
        return self._prune_unit(sql_unit, run_dir, validator)


@dataclass
class PruningResult:
    """Result of pruning analysis for a single SQL unit."""

    sql_key: str
    risks: list[dict[str, Any]]
    pruned_branches: list[str]
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

    detector = RiskDetector()
    start_time = datetime.now(timezone.utc)
    risks = detector.analyze(original_sql, sql_key)
    end_time = datetime.now(timezone.utc)

    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    pruned_branches = []
    for risk in risks:
        if risk.severity == "HIGH":
            pruned_branches.append(f"risk:{risk.risk_type}")

    result = {
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

    return result
