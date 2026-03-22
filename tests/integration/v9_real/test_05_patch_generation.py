"""
V9 Patch Stage Integration Test - Patch File Generation

Tests the PATCH stage which generates XML patch files from optimization proposals.
Validates patch structure, patch file creation, and SQL content.
"""

from pathlib import Path
import pytest

from sqlopt.application.v9_stages import run_stage

# Imports from conftest
from conftest import load_patches


# =============================================================================
# Test Class: TestV9Patch
# =============================================================================


class TestV9Patch:
    """Integration tests for V9 PATCH stage."""

    @pytest.fixture(scope="function")
    def complete_pipeline_dir(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> Path:
        """
        Run all 5 stages: init → parse → recognition → optimize → patch.

        This fixture ensures all previous stages complete before testing patch.
        """
        stages = ["init", "parse", "recognition", "optimize", "patch"]
        for stage in stages:
            result = run_stage(
                stage,
                temp_run_dir,
                config=real_mapper_config,
                validator=validator,
            )
            # Log result for debugging
            print(f"Stage {stage}: {result}")
            # Assert stage succeeded
            assert result.get("success", False), f"Stage {stage} failed: {result}"
        return temp_run_dir

    def test_patch_generates_patches_json(
        self, complete_pipeline_dir: Path, temp_run_dir: Path
    ) -> None:
        """
        Test that PATCH stage creates patch/patches.json file.

        Validates:
        - patch/patches.json is created
        - It contains a list of patch records
        """
        patches_path = complete_pipeline_dir / "patch" / "patches.json"
        assert patches_path.exists(), f"patches.json not found at {patches_path}"

        # Verify valid JSON
        patches_result = load_patches(complete_pipeline_dir)

        # Handle both dict with 'patches' key and direct list
        patches = (
            patches_result.get("patches", patches_result)
            if isinstance(patches_result, dict)
            else patches_result
        )

        assert isinstance(patches, list), "patches.json should contain a list"
        assert len(patches) > 0, "No patches generated"

    def test_patch_structure(
        self, complete_pipeline_dir: Path, temp_run_dir: Path
    ) -> None:
        """
        Test that each patch has required fields.

        Each patch should have:
        - sqlKey: the SQL key
        - applicable: boolean indicating if patch can be applied
        - patchFiles: list of patch file paths (if applicable)
        """
        patches_result = load_patches(complete_pipeline_dir)

        # Handle both dict with 'patches' key and direct list
        patches = (
            patches_result.get("patches", patches_result)
            if isinstance(patches_result, dict)
            else patches_result
        )

        assert len(patches) > 0, "No patches to validate"

        for i, patch in enumerate(patches):
            assert isinstance(patch, dict), f"Patch {i} is not a dict"

            # Verify required fields
            assert "sqlKey" in patch, f"Patch {i} missing sqlKey"
            assert "applicable" in patch, f"Patch {i} missing applicable"

            # Verify patchFiles field exists and is a list
            assert "patchFiles" in patch, f"Patch {i} missing patchFiles"
            assert isinstance(patch["patchFiles"], list), (
                f"Patch {i} patchFiles should be a list"
            )

    def test_patch_creates_patch_files_for_applicable(
        self, complete_pipeline_dir: Path, temp_run_dir: Path
    ) -> None:
        """
        Test that patch files are created for applicable proposals.

        For proposals where optimized SQL differs from original (applicable=True),
        verify that corresponding patch files are created in patch/patches/ directory.
        """
        patches_result = load_patches(complete_pipeline_dir)

        # Handle both dict with 'patches' key and direct list
        patches = (
            patches_result.get("patches", patches_result)
            if isinstance(patches_result, dict)
            else patches_result
        )

        patch_dir = complete_pipeline_dir / "patch" / "patches"

        applicable_patches = [p for p in patches if p.get("applicable") is True]

        if len(applicable_patches) == 0:
            pytest.skip("No applicable patches to verify")

        for patch in applicable_patches:
            sql_key = patch.get("sqlKey", "unknown")
            patch_files = patch.get("patchFiles", [])

            # If patch is applicable, it should have patchFiles
            assert len(patch_files) > 0, (
                f"Applicable patch {sql_key} missing patchFiles"
            )

            # Verify each referenced patch file exists
            for patch_file_ref in patch_files:
                # patch_file_ref could be full path or just filename
                if Path(patch_file_ref).is_absolute():
                    patch_file = Path(patch_file_ref)
                else:
                    patch_file = patch_dir / Path(patch_file_ref).name

                assert patch_file.exists(), (
                    f"Patch file not found: {patch_file} (referenced by {sql_key})"
                )

    def test_patch_patch_files_have_valid_sql(
        self, complete_pipeline_dir: Path, temp_run_dir: Path
    ) -> None:
        """
        Test that each patch file contains valid SQL content.

        Patch files should:
        - Contain non-empty SQL content
        - Start with comment header or SQL keyword
        """
        patches_result = load_patches(complete_pipeline_dir)

        # Handle both dict with 'patches' key and direct list
        patches = (
            patches_result.get("patches", patches_result)
            if isinstance(patches_result, dict)
            else patches_result
        )

        patch_dir = complete_pipeline_dir / "patch" / "patches"

        for patch in patches:
            if not patch.get("applicable"):
                continue

            sql_key = patch.get("sqlKey", "unknown")
            patch_files = patch.get("patchFiles", [])

            for patch_file_ref in patch_files:
                # Resolve patch file path
                if Path(patch_file_ref).is_absolute():
                    patch_file = Path(patch_file_ref)
                else:
                    patch_file = patch_dir / Path(patch_file_ref).name

                if not patch_file.exists():
                    continue  # Skip non-existent files (tested elsewhere)

                content = patch_file.read_text()
                assert len(content) > 0, (
                    f"Patch file for {sql_key} is empty: {patch_file}"
                )

                # Verify it contains SQL-related content
                # Patch files have format: "-- SQL Optimizer patch: {sql_key}\n-- Rule: {rule_name}\n{SQL}"
                lines = content.strip().split("\n")
                assert len(lines) >= 2, (
                    f"Patch file for {sql_key} should have header + SQL: {patch_file}"
                )

                # First lines should be comments
                assert lines[0].startswith("--"), (
                    f"Patch file for {sql_key} should start with comment: {patch_file}"
                )

    def test_patch_applicable_count_matches(
        self, complete_pipeline_dir: Path, temp_run_dir: Path
    ) -> None:
        """
        Test that patch stage correctly reports applicable count.

        The stage result should accurately reflect how many proposals
        resulted in applicable patches.
        """
        patches_result = load_patches(complete_pipeline_dir)

        # Handle both dict with 'patches' key and direct list
        patches = (
            patches_result.get("patches", patches_result)
            if isinstance(patches_result, dict)
            else patches_result
        )

        applicable_count = sum(1 for p in patches if p.get("applicable") is True)
        patch_files_count = len(
            list((complete_pipeline_dir / "patch" / "patches").glob("*.sql"))
        )

        # Number of patch files should match applicable count
        assert patch_files_count == applicable_count, (
            f"Patch files count ({patch_files_count}) should match "
            f"applicable count ({applicable_count})"
        )
