"""
V9 Recognition Stage Test - Real Database Baseline Collection

Tests the RECOGNITION stage which collects EXPLAIN data from real database.

Prerequisites:
- Init and Parse stages must have run first
- Real PostgreSQL database connection required
- Database should have users, orders, products tables

Run with:
    python -m pytest tests/integration/v9_real/test_03_recognition_db.py -v
"""

from __future__ import annotations

import pytest

from tests.integration.v9_real.conftest import (
    load_baselines,
    real_mapper_config,
    run_v9_stage,
    temp_run_dir,
    validator,
)


@pytest.fixture(scope="class")
def init_parse_recognition_dir(temp_run_dir, real_mapper_config, validator):
    """Run init → parse → recognition stages for recognition tests."""
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

    return temp_run_dir


class TestV9Recognition:
    """Tests for V9 Recognition Stage - Real Database Baseline Collection."""

    def test_recognition_collects_baselines(self, init_parse_recognition_dir):
        """Test that recognition stage collects baselines from real database."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        assert len(baselines) > 0, (
            "No baselines collected - recognition stage may have failed"
        )

    def test_recognition_baseline_has_required_fields(self, init_parse_recognition_dir):
        """Test that each baseline has required fields."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        assert len(baselines) > 0, "No baselines to validate"

        required_fields = [
            "sql_key",
            "execution_time_ms",
            "rows_scanned",
            "execution_plan",
            "database_platform",
        ]

        for baseline in baselines:
            for field in required_fields:
                assert field in baseline, f"Baseline missing required field: {field}"

            # execution_plan should be a dict with node_type
            assert isinstance(baseline["execution_plan"], dict), (
                f"execution_plan should be dict for {baseline.get('sql_key')}"
            )

    def test_recognition_execution_time_valid(self, init_parse_recognition_dir):
        """Test that execution_time_ms is a valid number >= 0."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        for baseline in baselines:
            assert "execution_time_ms" in baseline
            exec_time = baseline["execution_time_ms"]
            # execution_time_ms should be float and >= 0
            assert isinstance(exec_time, (int, float)), (
                f"execution_time_ms should be numeric for {baseline.get('sql_key')}"
            )
            assert exec_time >= 0, (
                f"execution_time_ms should be >= 0 for {baseline.get('sql_key')}"
            )

    def test_recognition_rows_scanned_valid(self, init_parse_recognition_dir):
        """Test that rows_scanned is a valid integer >= 0."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        for baseline in baselines:
            assert "rows_scanned" in baseline
            rows_scanned = baseline["rows_scanned"]
            # rows_scanned should be integer and >= 0
            assert isinstance(rows_scanned, int), (
                f"rows_scanned should be integer for {baseline.get('sql_key')}"
            )
            assert rows_scanned >= 0, (
                f"rows_scanned should be >= 0 for {baseline.get('sql_key')}"
            )

    def test_recognition_execution_plan_has_node_type(self, init_parse_recognition_dir):
        """Test that execution_plan has node_type field."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        for baseline in baselines:
            assert "execution_plan" in baseline
            plan = baseline["execution_plan"]
            assert "node_type" in plan, (
                f"execution_plan should have node_type for {baseline.get('sql_key')}"
            )

    def test_recognition_database_platform_is_postgresql(
        self, init_parse_recognition_dir
    ):
        """Test that database_platform is postgresql."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        for baseline in baselines:
            assert baseline.get("database_platform") == "postgresql", (
                f"Expected postgresql platform for {baseline.get('sql_key')}"
            )

    def test_recognition_handles_simple_query(self, init_parse_recognition_dir):
        """Test that testCountAll (SELECT COUNT(*) FROM users) has baseline."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        sql_key = "com.test.mapper.UserMapper.testCountAll"
        count_all_baselines = [b for b in baselines if b.get("sql_key") == sql_key]

        assert len(count_all_baselines) > 0, (
            f"No baseline found for {sql_key} - aggregate queries should still collect baselines"
        )

        # Verify the baseline is valid
        baseline = count_all_baselines[0]
        assert "execution_plan" in baseline
        assert "node_type" in baseline["execution_plan"]

    def test_recognition_explains_join_query(self, init_parse_recognition_dir):
        """Test that testInnerJoin collects baseline with join execution plan."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        sql_key = "com.test.mapper.UserMapper.testInnerJoin"
        join_baselines = [b for b in baselines if b.get("sql_key") == sql_key]

        assert len(join_baselines) > 0, (
            f"No baseline found for {sql_key} - join queries should collect baselines"
        )

        # Verify the baseline has join-related node type
        baseline = join_baselines[0]
        assert "execution_plan" in baseline
        node_type = baseline["execution_plan"].get("node_type", "").upper()

        # Join queries typically have these node types
        join_indicators = ["NESTED_LOOP", "HASH_JOIN", "MERGE_JOIN", "JOIN"]
        assert any(indicator in node_type for indicator in join_indicators), (
            f"Expected join node type for {sql_key}, got: {node_type}"
        )

    def test_recognition_baseline_file_exists(self, init_parse_recognition_dir):
        """Test that recognition/baselines.json file is created."""
        run_dir = init_parse_recognition_dir
        baselines_path = run_dir / "recognition" / "baselines.json"

        assert baselines_path.exists(), (
            "baselines.json file should exist after recognition stage"
        )

    def test_recognition_completes_without_error(self, init_parse_recognition_dir):
        """Test that recognition stage completes without critical errors."""
        run_dir = init_parse_recognition_dir
        baselines = load_baselines(run_dir)

        # Even if some baselines have errors, we should have some successful ones
        assert len(baselines) > 0, (
            "Recognition stage should produce at least some baselines"
        )
