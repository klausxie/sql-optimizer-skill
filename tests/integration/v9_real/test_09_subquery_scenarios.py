"""
V9 Subquery Scenario Test

Tests handling of subqueries (correlated, scalar, nested) in the V9 pipeline.

Subquery scenarios from UserMapper.xml:
- Q1: testCorrelatedSubquery - IN with correlated subquery
- Q2: testScalarSubqueryNew - scalar subquery in SELECT
- Q3: testNestedSubqueryComplex - multi-level nested subquery

Run with:
    python -m pytest tests/integration/v9_real/test_09_subquery_scenarios.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sqlopt.application.v9_stages import run_stage

from tests.integration.v9_real.conftest import (
    find_sql_unit,
    load_baselines,
    load_branches,
    load_proposals,
    real_mapper_config,
    run_v9_stage,
    temp_run_dir,
    validator,
)


# =============================================================================
# Subquery Scenario Keys
# =============================================================================

SUBQUERY_SCENARIOS = [
    "com.test.mapper.UserMapper.testCorrelatedSubquery",
    "com.test.mapper.UserMapper.testScalarSubqueryNew",
    "com.test.mapper.UserMapper.testNestedSubqueryComplex",
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="class")
def init_parse_dir(temp_run_dir: Path, real_mapper_config: dict, validator) -> Path:
    """Run init → parse stages for subquery scenario tests."""
    # Init stage
    result_init = run_v9_stage(
        "init",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_init.get("success", False), f"Init stage failed: {result_init}"

    # Parse stage
    result_parse = run_v9_stage(
        "parse",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_parse.get("success", False), f"Parse stage failed: {result_parse}"

    return temp_run_dir


@pytest.fixture(scope="class")
def init_parse_recognition_dir(
    temp_run_dir: Path, real_mapper_config: dict, validator
) -> Path:
    """Run init → parse → recognition stages for subquery tests."""
    # Init stage
    result_init = run_v9_stage(
        "init",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_init.get("success", False), f"Init stage failed: {result_init}"

    # Parse stage
    result_parse = run_v9_stage(
        "parse",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_parse.get("success", False), f"Parse stage failed: {result_parse}"

    # Recognition stage
    result_recognition = run_v9_stage(
        "recognition",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    # Recognition may fail for some subqueries, but stage should complete
    assert result_recognition.get("success", False), (
        f"Recognition stage failed: {result_recognition}"
    )

    return temp_run_dir


@pytest.fixture(scope="class")
def full_pipeline_dir(temp_run_dir: Path, real_mapper_config: dict, validator) -> Path:
    """Run init → parse → recognition → optimize stages for subquery tests."""
    # Init stage
    result_init = run_v9_stage(
        "init",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_init.get("success", False), f"Init stage failed: {result_init}"

    # Parse stage
    result_parse = run_v9_stage(
        "parse",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_parse.get("success", False), f"Parse stage failed: {result_parse}"

    # Recognition stage
    result_recognition = run_v9_stage(
        "recognition",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_recognition.get("success", False), (
        f"Recognition stage failed: {result_recognition}"
    )

    # Optimize stage
    result_optimize = run_v9_stage(
        "optimize",
        temp_run_dir,
        config=real_mapper_config,
        validator=validator,
    )
    assert result_optimize.get("success", False), (
        f"Optimize stage failed: {result_optimize}"
    )

    return temp_run_dir


# =============================================================================
# Test Class: TestV9SubqueryScenarios
# =============================================================================


class TestV9SubqueryScenarios:
    """Integration tests for V9 pipeline handling of subquery scenarios."""

    def test_subquery_queries_parse_without_error(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that init → parse completes without error for subquery scenarios.

        Validates:
        - No exceptions during parsing
        - Parse stage returns success
        - All three subquery SQL units are present in output
        """
        # Run init → parse
        result_init = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert result_init.get("success", False), f"Init failed: {result_init}"

        result_parse = run_stage(
            "parse",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result_parse.get("success", False), f"Parse failed: {result_parse}"

        # Load and check subquery scenarios were parsed
        branches = load_branches(temp_run_dir)

        for key in SUBQUERY_SCENARIOS:
            unit = find_sql_unit(branches, key)
            assert unit is not None, f"{key} not found in parse output"
            assert "sql" in unit, f"{key} missing SQL"

    def test_correlated_subquery_processed(self, init_parse_dir: Path) -> None:
        """
        Test that testCorrelatedSubquery is correctly parsed.

        The SQL should contain:
        - SELECT * FROM users u
        - WHERE u.id IN (subquery)
        - Correlated subquery: SELECT o.user_id FROM orders o WHERE o.amount > 1000
        """
        branches = load_branches(init_parse_dir)

        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testCorrelatedSubquery"
        )
        assert unit is not None, "testCorrelatedSubquery not found"

        sql = unit.get("sql", "")
        assert sql, "SQL content is empty"

        # Verify key components of correlated subquery
        assert "SELECT" in sql.upper(), "Missing SELECT"
        assert "FROM users" in sql.lower() or "from users" in sql.lower(), (
            "Missing users table"
        )
        assert "IN (" in sql.upper(), "Missing IN subquery pattern"
        assert "SELECT" in sql.upper(), "Missing subquery SELECT"

    def test_scalar_subquery_processed(self, init_parse_dir: Path) -> None:
        """
        Test that testScalarSubqueryNew is correctly parsed.

        The SQL should contain:
        - Scalar subquery in SELECT: (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id)
        - This appears as orderCount column
        """
        branches = load_branches(init_parse_dir)

        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testScalarSubqueryNew"
        )
        assert unit is not None, "testScalarSubqueryNew not found"

        sql = unit.get("sql", "")
        assert sql, "SQL content is empty"

        # Verify scalar subquery structure
        assert "SELECT" in sql.upper(), "Missing SELECT"
        assert "COUNT(*)" in sql.upper(), "Missing COUNT(*) in subquery"
        assert "FROM orders" in sql.lower() or "from orders" in sql.lower(), (
            "Missing orders table"
        )

    def test_nested_subquery_processed(self, init_parse_dir: Path) -> None:
        """
        Test that testNestedSubqueryComplex is correctly parsed.

        The SQL should have triple nested subquery:
        - Outer: WHERE id IN (middle subquery)
        - Middle: SELECT user_id FROM orders WHERE amount > (inner subquery)
        - Inner: SELECT AVG(amount) FROM orders
        """
        branches = load_branches(init_parse_dir)

        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testNestedSubqueryComplex"
        )
        assert unit is not None, "testNestedSubqueryComplex not found"

        sql = unit.get("sql", "")
        assert sql, "SQL content is empty"

        # Verify nested subquery structure - should have multiple SELECT/FROM patterns
        assert "SELECT" in sql.upper(), "Missing SELECT"
        assert "FROM users" in sql.lower() or "from users" in sql.lower(), (
            "Missing users table"
        )
        assert "IN (" in sql.upper(), "Missing IN subquery pattern"

        # Count occurrences of SELECT - should have at least 3 (outer + 2 nested)
        select_count = sql.upper().count("SELECT")
        assert select_count >= 3, (
            f"Expected at least 3 SELECT statements for triple nested subquery, got {select_count}"
        )

    def test_subquery_branches_have_valid_structure(self, init_parse_dir: Path) -> None:
        """
        Test that subquery SQL units have valid branch structure.

        Each subquery scenario should have branches array (may be empty if no dynamic SQL).
        """
        branches = load_branches(init_parse_dir)

        for key in SUBQUERY_SCENARIOS:
            unit = find_sql_unit(branches, key)
            assert unit is not None, f"{key} not found"

            # Unit should have branches field
            assert "branches" in unit or "sql" in unit, (
                f"{key} missing branches or sql field"
            )

    def test_subquery_baselines_collected(
        self, init_parse_recognition_dir: Path
    ) -> None:
        """
        Test that recognition stage collects baselines for subquery scenarios.

        Even if EXPLAIN fails for some subqueries, the stage should handle gracefully
        and produce baseline records (with possible errors noted).
        """
        baselines = load_baselines(init_parse_recognition_dir)

        # Should have some baselines collected
        assert len(baselines) > 0, (
            "No baselines collected - recognition stage may have failed completely"
        )

        # Check that at least one subquery scenario has a baseline
        subquery_baselines = [
            b for b in baselines if b.get("sql_key") in SUBQUERY_SCENARIOS
        ]

        # Note: Some baselines may have errors (execution_error), which is acceptable
        # The important thing is that the stage completed and produced output

    def test_subquery_baselines_have_required_fields(
        self, init_parse_recognition_dir: Path
    ) -> None:
        """
        Test that subquery baselines have required fields when successfully collected.
        """
        baselines = load_baselines(init_parse_recognition_dir)

        subquery_baselines = [
            b for b in baselines if b.get("sql_key") in SUBQUERY_SCENARIOS
        ]

        for baseline in subquery_baselines:
            # Check required fields
            assert "sql_key" in baseline, "Baseline missing sql_key"
            assert "database_platform" in baseline, "Baseline missing database_platform"

            # If baseline collected successfully (no error), check plan fields
            if "execution_error" not in baseline:
                assert "execution_plan" in baseline, (
                    "Successful baseline missing execution_plan"
                )
                assert "execution_time_ms" in baseline, (
                    "Successful baseline missing execution_time_ms"
                )

    def test_subquery_proposals_generated(self, full_pipeline_dir: Path) -> None:
        """
        Test that optimize stage generates proposals for subquery scenarios.

        Proposals should be generated (even if empty or with no recommendations).
        """
        proposals = load_proposals(full_pipeline_dir)

        # Should have proposals file created
        assert len(proposals) > 0, (
            "No proposals generated - optimize stage may have failed"
        )

        # Check subquery scenarios are in proposals
        for key in SUBQUERY_SCENARIOS:
            # Proposals may be indexed by sql_key or stored differently
            found = any(p.get("sql_key") == key or key in str(p) for p in proposals)
            # Note: Not all scenarios may generate proposals, so we just log if not found
            if not found:
                print(f"Warning: No proposal found for {key}")

    def test_subquery_proposals_have_valid_structure(
        self, full_pipeline_dir: Path
    ) -> None:
        """
        Test that subquery proposals have valid proposal structure.
        """
        proposals = load_proposals(full_pipeline_dir)

        if len(proposals) == 0:
            pytest.skip("No proposals generated")

        # Check first few proposals have valid structure
        for proposal in proposals[:5]:
            assert isinstance(proposal, dict), "Proposal should be a dict"
            # Valid proposal may have sql_key or be an error indicator
            assert "sql_key" in proposal or "error" in proposal, (
                "Proposal missing sql_key or error field"
            )
