"""Patch stage execute_one entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import read_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from sqlopt.stages.patch.patch_generator import (
    execute_one as generate_patch,
    PatchGenerator,
    PatchResult,
)


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
class PatchStage(Stage):
    """Patch stage implementation for V8 architecture."""

    name: str = "patch"
    version: str = "1.0.0"
    dependencies: list[str] = ["validate"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        if not paths.acceptance_path.exists():
            return StageResult(
                success=False,
                output_files=[],
                artifacts={},
                errors=[f"input file not found: {paths.acceptance_path}"],
                warnings=[],
            )

        acceptances = [row for row in read_jsonl(paths.acceptance_path) if isinstance(row, dict)]
        sql_units = _load_sql_units(run_dir)
        patches: list[dict[str, Any]] = []
        for acceptance in acceptances:
            try:
                validator.validate_stage_input("patch", acceptance)
                sql_key = str(acceptance.get("sqlKey") or "unknown")
                sql_unit = sql_units.get(sql_key)
                if sql_unit is None:
                    raise ValueError(f"sql unit not found for acceptance: {sql_key}")
                patch_result = self.execute_one(
                    sql_unit=sql_unit,
                    acceptance=acceptance,
                    run_dir=run_dir,
                    validator=validator,
                    config=self.config,
                )
                patches.append(patch_result)
            except Exception as exc:
                errors.append(f"error generating patch: {exc}")

        if patches:
            write_jsonl(paths.patches_path, patches)
        else:
            write_jsonl(paths.patches_path, [])

        log_event(
            paths.manifest_path,
            "patch",
            "done",
            {
                "run_id": context.run_id,
                "total_count": len(patches),
                "applicable_count": sum(1 for p in patches if p.get("applicable")),
            },
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=[paths.patches_path],
            artifacts={
                "patches": patches,
                "patch_count": len(patches),
                "applicable_count": sum(1 for p in patches if p.get("applicable")),
            },
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
        return generate_patch(
            sql_unit=sql_unit,
            acceptance=acceptance,
            run_dir=run_dir,
            validator=validator,
            config=config,
        )

    def get_input_contracts(self) -> list[str]:
        return ["acceptance_result"]

    def get_output_contracts(self) -> list[str]:
        return ["patch_result"]


def execute_one(
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return generate_patch(
        sql_unit=sql_unit,
        acceptance=acceptance,
        run_dir=run_dir,
        validator=validator,
        config=config,
    )


__all__ = ["PatchStage", "execute_one", "PatchGenerator", "PatchResult"]
