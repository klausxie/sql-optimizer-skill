"""
V9 Real Integration Tests - Validation Helper Functions

Provides utility functions for validating V9 pipeline stage outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StageOutputValidator:
    """Helper class for validating V9 stage outputs."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    # --- Init Stage ---

    def validate_init_output(self) -> tuple[bool, str]:
        """Validate init stage output files exist and are valid."""
        init_dir = self.run_dir / "init"
        sql_units_path = init_dir / "sql_units.json"

        if not sql_units_path.exists():
            return False, f"sql_units.json not found at {sql_units_path}"

        try:
            with open(sql_units_path) as f:
                sql_units = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in sql_units.json: {e}"

        if not isinstance(sql_units, list):
            return False, f"sql_units.json should be a list, got {type(sql_units)}"

        if len(sql_units) == 0:
            return False, "No SQL units found in sql_units.json"

        # Validate required fields
        required_fields = ["sqlKey", "namespace", "statementId", "statementType", "sql"]
        for i, unit in enumerate(sql_units):
            for field in required_fields:
                if field not in unit:
                    return False, f"Unit {i} missing required field: {field}"

        return True, f"Valid: {len(sql_units)} SQL units"

    # --- Parse Stage ---

    def validate_parse_output(self) -> tuple[bool, str]:
        """Validate parse stage output has branches."""
        parse_dir = self.run_dir / "parse"
        branches_path = parse_dir / "sql_units_with_branches.json"
        risks_path = parse_dir / "risks.json"

        if not branches_path.exists():
            return False, f"sql_units_with_branches.json not found"

        try:
            with open(branches_path) as f:
                units = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

        if not isinstance(units, list):
            return False, "Expected list of SQL units"

        # Check that each unit has branches
        units_with_branches = sum(1 for u in units if "branches" in u)
        if units_with_branches == 0:
            return False, "No units have branches - parse may have failed"

        # Validate branch structure
        for unit in units:
            if "branches" in unit:
                for branch in unit["branches"]:
                    if "sql" not in branch:
                        return (
                            False,
                            f"Branch missing 'sql' field in {unit.get('sqlKey')}",
                        )

        return True, f"Valid: {units_with_branches}/{len(units)} units have branches"

    # --- Recognition Stage ---

    def validate_recognition_output(self) -> tuple[bool, str]:
        """Validate recognition stage baseline collection."""
        rec_dir = self.run_dir / "recognition"
        baselines_path = rec_dir / "baselines.json"

        if not baselines_path.exists():
            return False, f"baselines.json not found"

        try:
            with open(baselines_path) as f:
                baselines = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

        if not isinstance(baselines, list):
            return False, "Expected list of baselines"

        if len(baselines) == 0:
            return False, "No baselines collected"

        # Validate baseline structure
        required_fields = [
            "sql_key",
            "execution_time_ms",
            "rows_scanned",
            "execution_plan",
        ]
        for i, baseline in enumerate(baselines):
            for field in required_fields:
                if field not in baseline:
                    return False, f"Baseline {i} missing field: {field}"

        return True, f"Valid: {len(baselines)} baselines"

    # --- Optimize Stage ---

    def validate_optimize_output(self) -> tuple[bool, str]:
        """Validate optimize stage proposal generation."""
        opt_dir = self.run_dir / "optimize"
        proposals_path = opt_dir / "proposals.json"

        if not proposals_path.exists():
            return False, f"proposals.json not found"

        try:
            with open(proposals_path) as f:
                proposals = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

        if not isinstance(proposals, list):
            return False, "Expected list of proposals"

        # Validate proposal structure
        valid_verdicts = {"ACTIONABLE", "NO_ACTION", "ERROR"}
        for i, proposal in enumerate(proposals):
            if "sqlKey" not in proposal:
                return False, f"Proposal {i} missing sqlKey"
            if "verdict" not in proposal:
                return False, f"Proposal {i} missing verdict"
            if proposal["verdict"] not in valid_verdicts:
                return False, f"Proposal {i} has invalid verdict: {proposal['verdict']}"

        return True, f"Valid: {len(proposals)} proposals"

    # --- Patch Stage ---

    def validate_patch_output(self) -> tuple[bool, str]:
        """Validate patch stage generates patches."""
        patch_dir = self.run_dir / "patch"
        patches_path = patch_dir / "patches.json"

        if not patches_path.exists():
            return False, f"patches.json not found"

        try:
            with open(patches_path) as f:
                result = json.load(f)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

        patches = result if isinstance(result, list) else result.get("patches", [])

        # Check patch files exist
        patch_files_dir = patch_dir / "patches"
        actionable_patches = [p for p in patches if p.get("verdict") == "ACTIONABLE"]

        return (
            True,
            f"Valid: {len(patches)} patches, {len(actionable_patches)} actionable",
        )

    # --- Full Pipeline ---

    def validate_full_pipeline(self) -> tuple[bool, list[str]]:
        """Validate all 5 stages completed successfully."""
        errors = []

        # Check each stage directory exists
        for stage in ["init", "parse", "recognition", "optimize", "patch"]:
            stage_dir = self.run_dir / stage
            if not stage_dir.exists():
                errors.append(f"Stage directory missing: {stage}")

        if errors:
            return False, errors

        # Validate each stage
        validators = [
            ("init", self.validate_init_output),
            ("parse", self.validate_parse_output),
            ("recognition", self.validate_recognition_output),
            ("optimize", self.validate_optimize_output),
            ("patch", self.validate_patch_output),
        ]

        for stage_name, validator in validators:
            valid, msg = validator()
            if not valid:
                errors.append(f"{stage_name}: {msg}")

        if errors:
            return False, errors

        return True, ["All 5 stages validated successfully"]


def validate_stage_output(stage_name: str, run_dir: Path) -> tuple[bool, str]:
    """
    Convenience function to validate a single stage output.

    Usage:
        valid, msg = validate_stage_output("init", run_dir)
    """
    validator = StageOutputValidator(run_dir)
    method_name = f"validate_{stage_name}_output"
    if hasattr(validator, method_name):
        return getattr(validator, method_name)()
    return False, f"No validator for stage: {stage_name}"


def validate_full_pipeline_output(run_dir: Path) -> tuple[bool, list[str]]:
    """
    Convenience function to validate the full pipeline output.

    Usage:
        valid, errors = validate_full_pipeline_output(run_dir)
    """
    validator = StageOutputValidator(run_dir)
    return validator.validate_full_pipeline()
