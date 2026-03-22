"""
V9 Real Integration Tests - End-to-End Full Pipeline Test

This module validates the COMPLETE 5-stage V9 pipeline runs successfully
with real MyBatis XML files.

Test Class: TestV9FullPipeline
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Ensure python path is set
ROOT = Path(__file__).resolve().parents[4]
PYTHON_DIR = ROOT / "python"
import sys

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from sqlopt.contracts import ContractValidator
from sqlopt.application.v9_stages import run_stage

# Imports from conftest (pytest adds test directory to path)
from conftest import (
    load_sql_units,
    load_branches,
    load_baselines,
    load_proposals,
    load_patches,
    filter_sql_units,
)

# Import validation helper
from validate_helper import validate_full_pipeline_output


# =============================================================================
# Helper Functions
# =============================================================================


def run_full_pipeline(run_dir: Path, config: dict, validator) -> dict[str, Any]:
    """
    Run all 5 V9 stages sequentially and return results.

    Args:
        run_dir: Temporary run directory
        config: Configuration dict
        validator: ContractValidator instance

    Returns:
        Dict mapping stage name to result dict
    """
    stages = ["init", "parse", "recognition", "optimize", "patch"]
    results = {}
    for stage in stages:
        result = run_stage(
            stage,
            run_dir,
            config=config,
            validator=validator,
        )
        results[stage] = result
        if not result.get("success"):
            print(f"Stage {stage} failed: {result}")
    return results


# =============================================================================
# Test Class: TestV9FullPipeline
# =============================================================================


class TestV9FullPipeline:
    """End-to-end tests for the complete V9 5-stage pipeline."""

    def test_full_pipeline_runs_all_stages(
        self, temp_run_dir: Path, real_mapper_config: dict, validator: ContractValidator
    ):
        """
        Verify all 5 stages run sequentially and each returns success=True.

        Stages: init → parse → recognition → optimize → patch
        """
        results = run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # All 5 stages should be present in results
        expected_stages = ["init", "parse", "recognition", "optimize", "patch"]
        for stage in expected_stages:
            assert stage in results, f"Stage {stage} was not run"
            assert results[stage].get("success"), (
                f"Stage {stage} failed: {results[stage]}"
            )

    def test_full_pipeline_produces_valid_outputs(
        self, temp_run_dir: Path, real_mapper_config: dict, validator: ContractValidator
    ):
        """
        Verify all stage output files exist and are valid JSON.

        Expected outputs:
        - init/sql_units.json
        - parse/sql_units_with_branches.json
        - recognition/baselines.json
        - optimize/proposals.json
        - patch/patches.json
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Verify each output file exists and contains valid JSON
        expected_files = {
            "init/sql_units.json": list,
            "parse/sql_units_with_branches.json": list,
            "recognition/baselines.json": list,
            "optimize/proposals.json": list,
            "patch/patches.json": (dict, list),
        }

        for rel_path, expected_type in expected_files.items():
            file_path = temp_run_dir / rel_path
            assert file_path.exists(), f"Expected output file not found: {rel_path}"

            with open(file_path) as f:
                data = json.load(f)

            # Validate type
            if isinstance(expected_type, tuple):
                assert isinstance(data, expected_type), (
                    f"{rel_path} has wrong type: "
                    f"expected {expected_type}, got {type(data)}"
                )
            else:
                assert isinstance(data, expected_type), (
                    f"{rel_path} has wrong type: "
                    f"expected {expected_type}, got {type(data)}"
                )

    def test_full_pipeline_processes_core_scenarios(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
        selected_scenarios: list[str],
    ):
        """
        Verify the 20 core scenarios appear in the final proposals.

        Uses the selected_scenarios fixture which provides 20 core scenarios.
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        assert len(proposals) > 0, "No proposals generated"

        # Get sqlKeys from proposals
        proposal_keys = {p.get("sqlKey") for p in proposals}

        # Check that at least some of the selected scenarios are in proposals
        matched = [s for s in selected_scenarios if s in proposal_keys]
        assert len(matched) > 0, (
            f"None of the {len(selected_scenarios)} core scenarios found in proposals. "
            f"Proposal keys: {proposal_keys}"
        )

    def test_full_pipeline_validates_using_helper(
        self, temp_run_dir: Path, real_mapper_config: dict, validator: ContractValidator
    ):
        """
        Verify validate_full_pipeline_output() returns (True, [...])
        indicating all 5 stages are valid.
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Validate using helper
        valid, messages = validate_full_pipeline_output(temp_run_dir)
        assert valid, f"Pipeline validation failed: {messages}"
        assert len(messages) > 0, "Expected validation messages"

    def test_pipeline_result_structure(
        self, temp_run_dir: Path, real_mapper_config: dict, validator: ContractValidator
    ):
        """
        Verify each run_stage() call returns dict with required fields.

        Required fields:
        - success: bool
        - At least one count field (sql_units_count, baselines_count, etc.)
        """
        # Run each stage and verify result structure
        stage_counts = {
            "init": "sql_units_count",
            "parse": "sql_units_count",
            "recognition": "baselines_count",
            "optimize": "proposals_count",
            "patch": "patches_count",
        }

        for stage, count_field in stage_counts.items():
            result = run_stage(
                stage,
                temp_run_dir,
                config=real_mapper_config,
                validator=validator,
            )

            # Verify success field exists
            assert "success" in result, f"Stage {stage} result missing 'success' field"
            assert isinstance(result["success"], bool), (
                f"Stage {stage} 'success' should be bool, got {type(result['success'])}"
            )

            # Verify count field exists
            assert count_field in result, (
                f"Stage {stage} result missing '{count_field}' field"
            )
            assert isinstance(result[count_field], int), (
                f"Stage {stage} '{count_field}' should be int, got {type(result[count_field])}"
            )
