"""
V9 Real Integration Tests - Shared Fixtures and Configuration

This module provides pytest fixtures for running V9 pipeline tests
with real MyBatis XML files and real database connections.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

# Ensure python path is set
ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from sqlopt.contracts import ContractValidator
from sqlopt.application.v9_stages import run_stage


# =============================================================================
# Configuration
# =============================================================================

TEST_DB_HOST = os.environ.get("SQLOPT_TEST_HOST", "100.101.41.123")
TEST_DB_PORT = os.environ.get("SQLOPT_TEST_PORT", "5432")
TEST_DB_USER = os.environ.get("SQLOPT_TEST_USER", "postgres")
TEST_DB_PASSWORD = os.environ.get("SQLOPT_TEST_PASSWORD", "postgres")
TEST_DB_NAME = os.environ.get("SQLOPT_TEST_DB", "postgres")


def get_postgres_dsn(database: str = TEST_DB_NAME) -> str:
    """Get PostgreSQL DSN for testing."""
    return f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{database}"


# =============================================================================
# Core Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def root_path() -> Path:
    """Root path of the project."""
    return ROOT


@pytest.fixture(scope="session")
def real_mapper_path() -> Path:
    """Path to real MyBatis XML mapper files."""
    return (
        ROOT
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
    # root_path should be the project root (mybatis-test dir)
    # mapper_globs are relative to root_path
    return {
        "config_version": "v1",
        "project": {
            "root_path": str(real_mapper_path.parent.parent.parent.parent),
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
# Selected Test Scenarios (20 core scenarios from 95+ total)
# =============================================================================

# Basic scenarios (5)
CORE_SCENARIOS = [
    "com.test.mapper.UserMapper.testSingleIf",
    "com.test.mapper.UserMapper.testTwoIf",
    "com.test.mapper.UserMapper.testChooseOtherwise",
    "com.test.mapper.UserMapper.testWhereIf",
    "com.test.mapper.UserMapper.testSetIf",
]

# Complex scenarios (5)
COMPLEX_SCENARIOS = [
    "com.test.mapper.UserMapper.testFiveIf",
    "com.test.mapper.UserMapper.testChooseNestedChoose",
    "com.test.mapper.UserMapper.testDynamicOrderBy",
    "com.test.mapper.UserMapper.testBindIf",
    "com.test.mapper.UserMapper.testIfForeachComplex",
]

# Cross-file scenarios (3)
CROSSFILE_SCENARIOS = [
    "com.test.mapper.UserMapper.testCrossFileInclude",
    "com.test.mapper.UserMapper.testChainedCrossFileInclude",
    "com.test.mapper.UserMapper.testCrossFileInChoose",
]

# Aggregation scenarios (3)
AGGREGATION_SCENARIOS = [
    "com.test.mapper.UserMapper.testGroupByHaving",
    "com.test.mapper.UserMapper.testMultiAggFunction",
    "com.test.mapper.UserMapper.testConditionalSum",
]

# Pagination scenarios (2)
PAGINATION_SCENARIOS = [
    "com.test.mapper.UserMapper.testDynamicPagination",
    "com.test.mapper.UserMapper.testLimitOffset",
]

# Subquery scenarios (2)
SUBQUERY_SCENARIOS = [
    "com.test.mapper.UserMapper.testCorrelatedSubquery",
    "com.test.mapper.UserMapper.testScalarSubqueryNew",
]

# All 20 core scenarios combined
ALL_CORE_SCENARIOS = (
    CORE_SCENARIOS
    + COMPLEX_SCENARIOS
    + CROSSFILE_SCENARIOS
    + AGGREGATION_SCENARIOS
    + PAGINATION_SCENARIOS
)


@pytest.fixture(scope="session")
def selected_scenarios() -> list[str]:
    """20 core scenarios for focused testing."""
    return ALL_CORE_SCENARIOS


@pytest.fixture(scope="session")
def all_scenario_keys() -> list[str]:
    """All available scenario keys for comprehensive testing."""
    return [
        # Basic (1-10)
        "com.test.mapper.UserMapper.testSingleIf",
        "com.test.mapper.UserMapper.testTwoIf",
        "com.test.mapper.UserMapper.testThreeIf",
        "com.test.mapper.UserMapper.testFourIf",
        "com.test.mapper.UserMapper.testChooseWhen",
        "com.test.mapper.UserMapper.testChooseOtherwise",
        "com.test.mapper.UserMapper.testWhereIf",
        "com.test.mapper.UserMapper.testSetIf",
        "com.test.mapper.UserMapper.testForeachIn",
        "com.test.mapper.UserMapper.testTrim",
        # Complex (11-20)
        "com.test.mapper.UserMapper.testIfChoose",
        "com.test.mapper.UserMapper.testWhereMultipleIf",
        "com.test.mapper.UserMapper.testChooseMultipleIf",
        "com.test.mapper.UserMapper.testIfForeach",
        "com.test.mapper.UserMapper.testWhereChooseWhen",
        "com.test.mapper.UserMapper.testChooseWithMultipleIf",
        "com.test.mapper.UserMapper.testFiveIf",
        "com.test.mapper.UserMapper.testChooseNestedChoose",
        "com.test.mapper.UserMapper.testComplexConditions",
        "com.test.mapper.UserMapper.testDynamicOrderBy",
        # Aggregation (56-70)
        "com.test.mapper.UserMapper.testCountAll",
        "com.test.mapper.UserMapper.testCountByStatus",
        "com.test.mapper.UserMapper.testGroupBy",
        "com.test.mapper.UserMapper.testGroupByHaving",
        "com.test.mapper.UserMapper.testMultiAggFunction",
        # Cross-file (86-95)
        "com.test.mapper.UserMapper.testCrossFileInclude",
        "com.test.mapper.UserMapper.testChainedCrossFileInclude",
        "com.test.mapper.UserMapper.testCrossFileInChoose",
        # Subquery
        "com.test.mapper.UserMapper.testCorrelatedSubquery",
        "com.test.mapper.UserMapper.testScalarSubqueryNew",
        # OrderMapper
        "com.test.mapper.OrderMapper.findOrdersWithCommon",
        "com.test.mapper.OrderMapper.findOrdersByMode",
    ]


# =============================================================================
# Helper Functions
# =============================================================================


def run_v9_stage(
    stage_name: str,
    run_dir: Path,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    """
    Helper to run a V9 stage with proper error handling.

    Returns the stage result dict with at least {"success": bool, ...}
    """
    result = run_stage(
        stage_name,
        run_dir,
        config=config,
        validator=validator,
    )
    return result


def load_sql_units(run_dir: Path) -> list[dict[str, Any]]:
    """Load SQL units from init stage output."""
    sql_units_path = run_dir / "init" / "sql_units.json"
    if not sql_units_path.exists():
        return []
    with open(sql_units_path) as f:
        return json.load(f)


def load_branches(run_dir: Path) -> list[dict[str, Any]]:
    """Load SQL units with branches from parse stage output."""
    branches_path = run_dir / "parse" / "sql_units_with_branches.json"
    if not branches_path.exists():
        return []
    with open(branches_path) as f:
        return json.load(f)


def load_baselines(run_dir: Path) -> list[dict[str, Any]]:
    """Load baselines from recognition stage output."""
    baselines_path = run_dir / "recognition" / "baselines.json"
    if not baselines_path.exists():
        return []
    with open(baselines_path) as f:
        return json.load(f)


def load_proposals(run_dir: Path) -> list[dict[str, Any]]:
    """Load proposals from optimize stage output."""
    proposals_path = run_dir / "optimize" / "proposals.json"
    if not proposals_path.exists():
        return []
    with open(proposals_path) as f:
        return json.load(f)


def load_patches(run_dir: Path) -> dict[str, Any]:
    """Load patches from patch stage output."""
    patches_path = run_dir / "patch" / "patches.json"
    if not patches_path.exists():
        return {"patches": []}
    with open(patches_path) as f:
        return json.load(f)


def find_sql_unit(
    sql_units: list[dict[str, Any]], sql_key: str
) -> dict[str, Any] | None:
    """Find a SQL unit by its sqlKey."""
    for unit in sql_units:
        if unit.get("sqlKey") == sql_key:
            return unit
    return None


def filter_sql_units(
    sql_units: list[dict[str, Any]], sql_keys: list[str]
) -> list[dict[str, Any]]:
    """Filter SQL units to only those in sql_keys list."""
    return [u for u in sql_units if u.get("sqlKey") in sql_keys]
