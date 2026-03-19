"""Optimize stage execute_one function.

Handles optimization proposal generation for a single SQL unit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator, STAGE_BOUNDARIES
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .llm_optimizer import LLMOptimizer


def _build_optimization_proposal(
    sql_key: str,
    original_sql: str,
    namespace: str,
    statement_id: str,
    candidates: list[dict[str, Any]],
    trace: dict[str, Any],
) -> dict[str, Any]:
    """Build an optimization proposal dictionary."""
    return {
        "sqlKey": sql_key,
        "originalSql": original_sql,
        "namespace": namespace,
        "statementId": statement_id,
        "candidates": candidates,
        "trace": trace,
    }


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


@stage_registry.register
class OptimizeStage(Stage):
    """Optimize stage implementation for V8 architecture.

    Generates optimization proposals for SQL units using rule engine and LLM.
    """

    name: str = "optimize"
    version: str = "1.0.0"
    dependencies: list[str] = ["discovery", "baseline"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.optimizer = LLMOptimizer(self.config)

    def execute(self, context: StageContext) -> StageResult:
        """Execute the optimize stage.

        Args:
            context: Stage execution context containing run_id, config, and data_dir

        Returns:
            StageResult with optimization artifacts
        """
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        validator.validate_stage_input("optimize", {})

        optimizer = LLMOptimizer(self.config)

        # Load baseline results to get SQL units
        sql_units: list[dict[str, Any]] = []
        baseline_results: list[dict[str, Any]] = []

        # Load baseline results
        if paths.baseline_results_path.exists():
            try:
                with open(paths.baseline_results_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            record = json.loads(line)
                            baseline_results.append(record)
            except Exception as e:
                errors.append(f"failed to load baseline results: {e}")

        # Load scan units for SQL details
        if paths.scan_units_path.exists():
            try:
                with open(paths.scan_units_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            record = json.loads(line)
                            if "sqlUnits" in record:
                                sql_units.extend(record["sqlUnits"])
            except Exception as e:
                errors.append(f"failed to load SQL units: {e}")

        # Build a map of sql_key to baseline result
        baseline_map: dict[str, dict[str, Any]] = {}
        for br in baseline_results:
            sql_key = br.get("sql_key", "")
            if sql_key:
                baseline_map[sql_key] = br

        proposals: list[dict[str, Any]] = []

        for sql_unit in sql_units:
            try:
                sql_key = sql_unit.get(
                    "sqlKey",
                    sql_unit.get("namespace", "unknown")
                    + "."
                    + sql_unit.get("statementId", "unknown"),
                )
                original_sql = sql_unit.get("sql", "")

                # Try to get baseline info for context
                proposal_data: dict[str, Any] = {}
                if sql_key in baseline_map:
                    proposal_data = {"dbEvidenceSummary": {}, "issues": []}

                # Generate optimization candidates
                opt_result = optimizer.generate_optimizations(sql_unit, proposal_data)

                # Convert candidates to dict format
                candidates = []
                for candidate in opt_result.candidates:
                    candidates.append(
                        {
                            "id": candidate.id,
                            "source": candidate.source,
                            "rewrittenSql": candidate.rewritten_sql,
                            "rewriteStrategy": candidate.rewrite_strategy,
                            "semanticRisk": candidate.semantic_risk,
                            "confidence": candidate.confidence,
                            "improvement": candidate.improvement,
                        }
                    )

                proposal = _build_optimization_proposal(
                    sql_key=sql_key,
                    original_sql=original_sql,
                    namespace=sql_unit.get("namespace", ""),
                    statement_id=sql_unit.get("statementId", ""),
                    candidates=candidates,
                    trace=opt_result.trace,
                )

                validator.validate("optimization_proposal", proposal)
                append_jsonl(paths.proposals_path, proposal)
                proposals.append(proposal)

                log_event(
                    paths.manifest_path,
                    "optimize",
                    "done",
                    {"statement_key": sql_key},
                )

            except Exception as e:
                errors.append(f"error processing SQL unit: {e}")

        if proposals:
            try:
                validator.validate_stage_output("optimize", proposals[0])
            except Exception as e:
                errors.append(f"output validation error: {e}")

        artifacts = {
            "proposals": proposals,
            "total_count": len(proposals),
        }

        if paths.proposals_path.exists():
            output_files.append(paths.proposals_path)

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts=artifacts,
            errors=errors,
            warnings=warnings,
        )

    def get_input_contracts(self) -> list[str]:
        """Optimize stage expects baseline_result as input.

        Returns:
            List containing "baseline_result"
        """
        return ["baseline_result"]

    def get_output_contracts(self) -> list[str]:
        """Optimize stage outputs optimization_proposal.

        Returns:
            List containing "optimization_proposal"
        """
        return ["optimization_proposal"]

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Execute optimization for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Optimization proposal dictionary
        """
        return execute_one(sql_unit, run_dir, validator, self.config)


@dataclass
class OptimizationProposal:
    """Optimization proposal for a single SQL unit."""

    sql_key: str
    original_sql: str
    candidates: list[dict[str, Any]]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
