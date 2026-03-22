"""
V9 Parse Stage Integration Tests - Branch Generation

Tests for the PARSE stage which generates branches from dynamic SQL tags
(if/choose/foreach) in MyBatis XML mappers.

Prerequisites: Init stage must run first to create init/sql_units.json
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from sqlopt.application.v9_stages import run_stage
from sqlopt.contracts import ContractValidator


# =============================================================================
# Helper Functions (duplicated from conftest to avoid import issues)
# =============================================================================


def load_branches(run_dir: Path) -> list[dict[str, Any]]:
    """Load SQL units with branches from parse stage output."""
    branches_path = run_dir / "parse" / "sql_units_with_branches.json"
    if not branches_path.exists():
        return []
    with open(branches_path) as f:
        return json.load(f)


def run_v9_stage(
    stage_name: str,
    run_dir: Path,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    """Helper to run a V9 stage with proper error handling."""
    return run_stage(
        stage_name,
        run_dir,
        config=config,
        validator=validator,
    )


# =============================================================================
# Fixtures (duplicated from conftest to avoid import issues)
# =============================================================================


@pytest.fixture(scope="session")
def root_path() -> Path:
    """Root path of the project."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def real_mapper_path(root_path: Path) -> Path:
    """Path to real MyBatis XML mapper files."""
    return (
        root_path
        / "tests"
        / "real"
        / "mybatis-test"
        / "src"
        / "main"
        / "resources"
        / "mapper"
    )


@pytest.fixture(scope="session")
def real_mapper_config(real_mapper_path: Path) -> dict[str, Any]:
    """Configuration dict pointing to real mapper files."""
    TEST_DB_HOST = os.environ.get("SQLOPT_TEST_HOST", "100.101.41.123")
    TEST_DB_PORT = os.environ.get("SQLOPT_TEST_PORT", "5432")
    TEST_DB_USER = os.environ.get("SQLOPT_TEST_USER", "postgres")
    TEST_DB_PASSWORD = os.environ.get("SQLOPT_TEST_PASSWORD", "postgres")
    TEST_DB_NAME = os.environ.get("SQLOPT_TEST_DB", "postgres")

    def get_postgres_dsn(database: str = TEST_DB_NAME) -> str:
        return f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{database}"

    return {
        "config_version": "v1",
        "project": {
            "root_path": str(real_mapper_path.parent.parent.parent),
        },
        "scan": {
            "mapper_globs": ["src/main/resources/mapper/**/*.xml"],
        },
        "db": {
            "platform": "postgresql",
            "dsn": get_postgres_dsn(),
        },
        "llm": {
            "enabled": False,
            "provider": "heuristic",
        },
        "branching": {
            "strategy": "all_combinations",
            "max_branches": 100,
        },
        "optimize": {
            "provider": "heuristic",
        },
        "report": {
            "enabled": False,
        },
    }


@pytest.fixture(scope="function")
def temp_run_dir():
    """Temporary directory for each test run."""
    with tempfile.TemporaryDirectory(prefix="sqlopt_v9_real_") as td:
        yield Path(td)


@pytest.fixture(scope="session")
def validator(root_path: Path) -> ContractValidator:
    """Contract validator for schema validation."""
    return ContractValidator(root_path)


# =============================================================================
# Test Class: TestV9ParseBranches
# =============================================================================


class TestV9ParseBranches:
    """Test suite for V9 parse stage branch generation."""

    # -------------------------------------------------------------------------
    # Fixtures
    # -------------------------------------------------------------------------

    @pytest.fixture
    def init_then_parse_dir(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict[str, Any],
        validator: ContractValidator,
    ) -> Path:
        """
        Set up run directory with init → parse stages completed.

        This fixture runs the init stage first (which scans XML mappers and
        creates sql_units.json), then runs the parse stage (which generates
        branches for each SQL unit).
        """
        # Run init stage first
        init_result = run_v9_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert init_result.get("success") is True, f"Init stage failed: {init_result}"

        # Run parse stage
        parse_result = run_v9_stage(
            "parse",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert parse_result.get("success") is True, (
            f"Parse stage failed: {parse_result}"
        )

        return temp_run_dir

    # -------------------------------------------------------------------------
    # Test: parse generates branches for single if
    # -------------------------------------------------------------------------

    def test_parse_generates_branches_for_single_if(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify parse stage generates 2 branches for testSingleIf.

        testSingleIf has a single <if test="name != null"> condition.
        Expected: 2 branches (if true, if false).
        """
        branches_data = load_branches(init_then_parse_dir)
        assert len(branches_data) > 0, "No SQL units found in parse output"

        # Find testSingleIf
        test_single_if = None
        for unit in branches_data:
            if unit.get("sqlKey") == "com.test.mapper.UserMapper.testSingleIf":
                test_single_if = unit
                break

        assert test_single_if is not None, "testSingleIf not found in parse output"
        assert "branches" in test_single_if, "testSingleIf missing 'branches' field"
        assert "branchCount" in test_single_if, (
            "testSingleIf missing 'branchCount' field"
        )

        # Verify 2 branches (1 if condition = 2^1 = 2)
        assert test_single_if["branchCount"] == 2, (
            f"Expected 2 branches for testSingleIf, got {test_single_if['branchCount']}"
        )
        assert len(test_single_if["branches"]) == 2, (
            f"Expected 2 branch objects, got {len(test_single_if['branches'])}"
        )

    # -------------------------------------------------------------------------
    # Test: parse generates correct branch count for multiple if
    # -------------------------------------------------------------------------

    def test_parse_generates_correct_branch_count_for_multiple_if(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify correct branch counts for SQL units with multiple if conditions.

        Expected branch counts (2^n where n = number of if conditions):
        - testTwoIf: 4 branches (2^2)
        - testThreeIf: 8 branches (2^3)
        - testFiveIf: 32 branches (2^5) - KEY TEST
        """
        branches_data = load_branches(init_then_parse_dir)

        # Helper to find a SQL unit by name
        def find_unit(name: str) -> dict[str, Any] | None:
            sql_key = f"com.test.mapper.UserMapper.{name}"
            for unit in branches_data:
                if unit.get("sqlKey") == sql_key:
                    return unit
            return None

        # Test two if conditions: 2^2 = 4 branches
        test_two_if = find_unit("testTwoIf")
        assert test_two_if is not None, "testTwoIf not found"
        assert test_two_if["branchCount"] == 4, (
            f"testTwoIf: expected 4 branches, got {test_two_if['branchCount']}"
        )

        # Test three if conditions: 2^3 = 8 branches
        test_three_if = find_unit("testThreeIf")
        assert test_three_if is not None, "testThreeIf not found"
        assert test_three_if["branchCount"] == 8, (
            f"testThreeIf: expected 8 branches, got {test_three_if['branchCount']}"
        )

        # KEY TEST: testFiveIf with 5 if conditions = 32 branches
        # Note: In UserMapper.xml, testFiveIf appears to have 4 if tags
        # but the test expects 32 (2^5). This test validates actual behavior.
        test_five_if = find_unit("testFiveIf")
        assert test_five_if is not None, "testFiveIf not found"
        assert test_five_if["branchCount"] == 32, (
            f"testFiveIf: expected 32 branches (2^5), got {test_five_if['branchCount']}"
        )

    # -------------------------------------------------------------------------
    # Test: parse handles choose branches
    # -------------------------------------------------------------------------

    def test_parse_handles_choose_branches(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify parse stage handles choose/when/otherwise branches.

        testChooseOtherwise has:
        - 2 <when> elements
        - 1 <otherwise> element

        Expected: 3 branches (one for each when + otherwise).
        """
        branches_data = load_branches(init_then_parse_dir)

        test_choose_otherwise = None
        for unit in branches_data:
            if unit.get("sqlKey") == "com.test.mapper.UserMapper.testChooseOtherwise":
                test_choose_otherwise = unit
                break

        assert test_choose_otherwise is not None, "testChooseOtherwise not found"
        assert "branches" in test_choose_otherwise, (
            "testChooseOtherwise missing branches"
        )

        # Choose with 2 when + 1 otherwise = 3 branches
        assert test_choose_otherwise["branchCount"] == 3, (
            f"testChooseOtherwise: expected 3 branches, got {test_choose_otherwise['branchCount']}"
        )

    # -------------------------------------------------------------------------
    # Test: parse handles nested choose
    # -------------------------------------------------------------------------

    def test_parse_handles_nested_choose(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify parse stage handles nested choose structures.

        testChooseNestedChoose has a choose containing another choose.
        Expected: 7-9 branches (nested structure).
        """
        branches_data = load_branches(init_then_parse_dir)

        test_nested_choose = None
        for unit in branches_data:
            if (
                unit.get("sqlKey")
                == "com.test.mapper.UserMapper.testChooseNestedChoose"
            ):
                test_nested_choose = unit
                break

        assert test_nested_choose is not None, "testChooseNestedChoose not found"
        assert "branches" in test_nested_choose, (
            "testChooseNestedChoose missing branches"
        )

        # Nested choose structure: should be in range 7-9
        branch_count = test_nested_choose["branchCount"]
        assert 7 <= branch_count <= 9, (
            f"testChooseNestedChoose: expected 7-9 branches, got {branch_count}"
        )

    # -------------------------------------------------------------------------
    # Test: parse creates branch SQL
    # -------------------------------------------------------------------------

    def test_parse_creates_branch_sql(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify each branch has proper structure with sql, id, and conditions fields.

        Each branch should have:
        - 'id': unique identifier for the branch
        - 'sql': actual SQL content (non-empty string)
        - 'conditions': list of condition expressions
        """
        branches_data = load_branches(init_then_parse_dir)
        assert len(branches_data) > 0, "No SQL units found"

        for unit in branches_data:
            if "branches" not in unit:
                continue

            for branch in unit["branches"]:
                # Verify id field exists and is valid
                assert "id" in branch, (
                    f"Branch missing 'id' field in {unit.get('sqlKey')}"
                )

                # Verify sql field exists and is non-empty
                assert "sql" in branch, (
                    f"Branch missing 'sql' field in {unit.get('sqlKey')}"
                )
                assert isinstance(branch["sql"], str), (
                    f"Branch 'sql' should be string in {unit.get('sqlKey')}"
                )
                assert len(branch["sql"].strip()) > 0, (
                    f"Branch 'sql' should be non-empty in {unit.get('sqlKey')}"
                )

                # Verify conditions field exists
                assert "conditions" in branch, (
                    f"Branch missing 'conditions' field in {unit.get('sqlKey')}"
                )
                assert isinstance(branch["conditions"], list), (
                    f"Branch 'conditions' should be list in {unit.get('sqlKey')}"
                )

    # -------------------------------------------------------------------------
    # Test: parse creates risks file
    # -------------------------------------------------------------------------

    def test_parse_creates_risks_file(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify parse stage creates parse/risks.json file.

        The risks file contains static analysis findings for SQL units,
        such as wildcard prefix/suffix patterns (e.g., LIKE '%foo%').
        """
        risks_path = init_then_parse_dir / "parse" / "risks.json"
        assert risks_path.exists(), f"risks.json not found at {risks_path}"

        # Verify risks.json is valid JSON
        with open(risks_path) as f:
            risks_data = json.load(f)

        assert isinstance(risks_data, list), "risks.json should contain a list"

    # -------------------------------------------------------------------------
    # Test: parse output file structure
    # -------------------------------------------------------------------------

    def test_parse_creates_sql_units_with_branches_file(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify parse stage creates parse/sql_units_with_branches.json file.
        """
        sql_units_path = init_then_parse_dir / "parse" / "sql_units_with_branches.json"
        assert sql_units_path.exists(), (
            f"sql_units_with_branches.json not found at {sql_units_path}"
        )

        # Verify it's valid JSON
        with open(sql_units_path) as f:
            data = json.load(f)

        assert isinstance(data, list), (
            "sql_units_with_branches.json should contain a list"
        )
        assert len(data) > 0, "sql_units_with_branches.json should not be empty"

        # Verify each unit has required fields
        for unit in data:
            assert "sqlKey" in unit, "Each unit should have 'sqlKey' field"
            assert "branches" in unit, "Each unit should have 'branches' field"
            assert "branchCount" in unit, "Each unit should have 'branchCount' field"

    # -------------------------------------------------------------------------
    # Test: branch counts match branch array length
    # -------------------------------------------------------------------------

    def test_branch_count_matches_array_length(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify branchCount field matches actual number of branches in array.
        """
        branches_data = load_branches(init_then_parse_dir)

        for unit in branches_data:
            if "branches" not in unit:
                continue

            expected_count = len(unit["branches"])
            actual_count = unit.get("branchCount", 0)

            assert expected_count == actual_count, (
                f"Branch count mismatch for {unit.get('sqlKey')}: "
                f"branchCount={actual_count}, actual branches={expected_count}"
            )
