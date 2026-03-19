"""Patch stage execute_one entry point.

This module provides PatchStage class for V8 architecture and
re-exports the execute_one function from patch_generator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from sqlopt.stages.patch.patch_generator import (
    execute_one as generate_patch,
    PatchGenerator,
    PatchResult,
)


@stage_registry.register
class PatchStage(Stage):
    """Patch stage implementation for V8 architecture.

    Generates XML patches from validated optimization candidates.
    """

    name: str = "patch"
    version: str = "1.0.0"
    dependencies: list[str] = ["optimize", "validate"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        """Execute the patch stage.

        Args:
            context: Stage execution context containing run_id, config, and data_dir

        Returns:
            StageResult with patch artifacts
        """
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        # Get acceptances from validate stage output
        acceptance_path = paths.acceptance_path
        if not acceptance_path.exists():
            warnings.append("no acceptance results found, skipping patch generation")
            return StageResult(
                success=True,
                output_files=output_files,
                artifacts=artifacts,
                errors=errors,
                warnings=warnings,
            )

        # Read all acceptances
        acceptances: list[dict[str, Any]] = []
        try:
            with open(acceptance_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        acceptances.append(eval(line))
        except Exception as e:
            errors.append(f"error reading acceptances: {e}")
            return StageResult(
                success=False,
                output_files=output_files,
                artifacts=artifacts,
                errors=errors,
                warnings=warnings,
            )

        if not acceptances:
            warnings.append("no acceptances to process for patch generation")

        # Process each acceptance
        patches: list[dict[str, Any]] = []
        for acceptance in acceptances:
            try:
                sql_unit = acceptance.get("sql_unit", {})
                patch_result = self.execute_one(
                    sql_unit=sql_unit,
                    acceptance=acceptance,
                    run_dir=run_dir,
                    validator=validator,
                    config=self.config,
                )
                patches.append(patch_result)
            except Exception as e:
                errors.append(f"error generating patch: {e}")

        # Build artifacts
        artifacts = {
            "patches": patches,
            "total_count": len(patches),
            "selected_count": sum(1 for p in patches if p.get("status") == "selected"),
            "skipped_count": sum(1 for p in patches if p.get("status") == "skipped"),
        }

        # Log completion
        log_event(
            paths.manifest_path,
            "patch",
            "done",
            {
                "run_id": context.run_id,
                "total_count": len(patches),
                "selected_count": artifacts["selected_count"],
                "skipped_count": artifacts["skipped_count"],
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
        acceptance: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute patch generation for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            acceptance: Acceptance result from validate stage
            run_dir: Run directory
            validator: Contract validator
            config: Optional configuration

        Returns:
            Patch result dictionary
        """
        return generate_patch(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )

    def get_input_contracts(self) -> list[str]:
        """Patch stage expects acceptance input.

        Returns:
            List containing "acceptance"
        """
        return ["acceptance"]

    def get_output_contracts(self) -> list[str]:
        """Patch stage outputs patch_result.

        Returns:
            List containing "patch_result"
        """
        return ["patch_result"]


def execute_one(
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute patch generation for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        acceptance: Acceptance result from validate stage
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Patch result dictionary
    """
    return generate_patch(
        sql_unit=sql_unit,
        acceptance=acceptance,
        run_dir=run_dir,
        validator=validator,
        config=config,
    )


__all__ = ["PatchStage", "execute_one", "PatchGenerator", "PatchResult"]
