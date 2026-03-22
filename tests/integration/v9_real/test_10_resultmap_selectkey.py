"""
V9 resultMap and selectKey Parsing Integration Tests

Tests that resultMap and selectKey tags are parsed correctly without
crashing the V9 pipeline. These are MyBatis-specific tags that affect
result mapping, not SQL execution, so the optimizer should parse them
without error.

Scenarios covered:
- R1-R6: resultMap scenarios (association, collection, discriminator)
- S1-S4: selectKey scenarios (sequence, UUID, auto-increment)

Prerequisites: Init stage must run first to create init/sql_units.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sqlopt.application.v9_stages import run_stage
from sqlopt.contracts import ContractValidator

# Import fixtures from conftest
from conftest import (
    load_branches,
    real_mapper_config,
    run_v9_stage,
    temp_run_dir,
    validator,
    find_sql_unit,
)


# =============================================================================
# Test Class: TestV9ResultMapSelectKey
# =============================================================================


class TestV9ResultMapSelectKey:
    """Test suite for V9 resultMap and selectKey parsing."""

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

        Runs init stage (which scans XML mappers and creates sql_units.json),
        then runs parse stage (which generates branches for each SQL unit).
        """
        # Run init stage
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
    # Test: resultMap - Association (R1)
    # -------------------------------------------------------------------------

    def test_resultmap_association_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testResultMapAssociation with <association> tag is parsed.

        The <association> tag is used for JOIN results (one-to-one mapping).
        The SQL should contain a JOIN between users and orders tables.
        """
        branches = load_branches(init_then_parse_dir)

        # Find the resultMap association scenario
        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testResultMapAssociation"
        )
        assert unit is not None, "testResultMapAssociation not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

        # SQL should contain JOIN for association mapping
        sql = unit["sql"].upper()
        assert "JOIN" in sql, f"Expected JOIN in resultMap association SQL: {sql[:200]}"

    # -------------------------------------------------------------------------
    # Test: resultMap - Collection (R2)
    # -------------------------------------------------------------------------

    def test_resultmap_collection_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testResultMapCollection with <collection> tag is parsed.

        The <collection> tag is used for one-to-many mapping (e.g., user orders).
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testResultMapCollection"
        )
        assert unit is not None, "testResultMapCollection not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

        # SQL should be valid (can have JOIN for collection)
        sql = unit["sql"].upper()
        assert len(sql.strip()) > 0, "SQL should not be empty"

    # -------------------------------------------------------------------------
    # Test: resultMap - No ID (R3)
    # -------------------------------------------------------------------------

    def test_resultmap_no_id_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testResultMapNoId with resultMap lacking <id> is parsed.

        This is a diagnostic scenario - resultMap without id column.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testResultMapNoId")
        assert unit is not None, "testResultMapNoId not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

    # -------------------------------------------------------------------------
    # Test: resultMap - Nested Select N+1 (R4)
    # -------------------------------------------------------------------------

    def test_nested_select_n1_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testNestedSelectN1 with nested select pattern is parsed.

        This is the N+1 problem pattern where collection uses nested select.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testNestedSelectN1")
        assert unit is not None, "testNestedSelectN1 not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

    # -------------------------------------------------------------------------
    # Test: resultMap - Nested Result (R5)
    # -------------------------------------------------------------------------

    def test_nested_result_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testNestedResult with nested result pattern is parsed.

        This is the correct way to handle one-to-many with JOIN.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testNestedResult")
        assert unit is not None, "testNestedResult not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

        # Should contain JOIN
        sql = unit["sql"].upper()
        assert "JOIN" in sql, f"Expected JOIN in nested result SQL: {sql[:200]}"

    # -------------------------------------------------------------------------
    # Test: resultMap - Discriminator (R6)
    # -------------------------------------------------------------------------

    def test_resultmap_discriminator_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testDiscriminator with <discriminator> tag is parsed.

        The <discriminator> tag is used for type-based result mapping.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testDiscriminator")
        assert unit is not None, "testDiscriminator not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

    # -------------------------------------------------------------------------
    # Test: selectKey - Oracle Style (S1)
    # -------------------------------------------------------------------------

    def test_selectkey_oracle_style_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testSelectKeyOracle with SELECT before INSERT is parsed.

        Oracle-style: SELECT key generation BEFORE INSERT.
        Uses SELECT COALESCE(MAX(id), 0) + 1 FROM users pattern.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testSelectKeyOracle")
        assert unit is not None, "testSelectKeyOracle not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

        # SQL should contain SELECT before INSERT (BEFORE order)
        sql = unit["sql"].upper()
        assert "SELECT" in sql, f"Expected SELECT in selectKey Oracle SQL: {sql[:200]}"

    # -------------------------------------------------------------------------
    # Test: selectKey - PostgreSQL Style (S2)
    # -------------------------------------------------------------------------

    def test_selectkey_postgres_style_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testSelectKeyPostgres with PostgreSQL sequence style is parsed.

        PostgreSQL-style: Similar to Oracle with SELECT BEFORE INSERT.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(
            branches, "com.test.mapper.UserMapper.testSelectKeyPostgres"
        )
        assert unit is not None, "testSelectKeyPostgres not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

    # -------------------------------------------------------------------------
    # Test: selectKey - MySQL Style (S3)
    # -------------------------------------------------------------------------

    def test_selectkey_mysql_style_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testSelectKeyMysql with SELECT after INSERT is parsed.

        MySQL-style: SELECT key generation AFTER INSERT for auto-increment.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testSelectKeyMysql")
        assert unit is not None, "testSelectKeyMysql not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

        # SQL should contain SELECT (AFTER order)
        sql = unit["sql"].upper()
        assert "SELECT" in sql, f"Expected SELECT in selectKey MySQL SQL: {sql[:200]}"

    # -------------------------------------------------------------------------
    # Test: selectKey - UUID Style (S4)
    # -------------------------------------------------------------------------

    def test_selectkey_uuid_style_parsed(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify testSelectKeyUuid with UUID/random generation is parsed.

        UUID-style: SELECT FLOOR(RAND() * 1000000) for key generation.
        """
        branches = load_branches(init_then_parse_dir)

        unit = find_sql_unit(branches, "com.test.mapper.UserMapper.testSelectKeyUuid")
        assert unit is not None, "testSelectKeyUuid not found in parse output"
        assert "sql" in unit, "Unit missing 'sql' field"

    # -------------------------------------------------------------------------
    # Test: All resultMap and selectKey scenarios in parse output
    # -------------------------------------------------------------------------

    def test_all_resultmap_selectkey_scenarios_found(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify all resultMap (R1-R6) and selectKey (S1-S4) scenarios are found.

        These are MyBatis-specific tags that should be parsed without error.
        """
        branches = load_branches(init_then_parse_dir)

        # All expected scenario keys
        expected_scenarios = [
            # resultMap scenarios
            "com.test.mapper.UserMapper.testResultMapAssociation",
            "com.test.mapper.UserMapper.testResultMapCollection",
            "com.test.mapper.UserMapper.testResultMapNoId",
            "com.test.mapper.UserMapper.testNestedSelectN1",
            "com.test.mapper.UserMapper.testNestedResult",
            "com.test.mapper.UserMapper.testDiscriminator",
            # selectKey scenarios
            "com.test.mapper.UserMapper.testSelectKeyOracle",
            "com.test.mapper.UserMapper.testSelectKeyPostgres",
            "com.test.mapper.UserMapper.testSelectKeyMysql",
            "com.test.mapper.UserMapper.testSelectKeyUuid",
        ]

        found_scenarios = []
        missing_scenarios = []

        for sql_key in expected_scenarios:
            unit = find_sql_unit(branches, sql_key)
            if unit is not None:
                found_scenarios.append(sql_key)
            else:
                missing_scenarios.append(sql_key)

        assert len(missing_scenarios) == 0, (
            f"Missing scenarios: {missing_scenarios}. "
            f"Found {len(found_scenarios)}/{len(expected_scenarios)} scenarios. "
            f"Missing: {missing_scenarios}"
        )

    # -------------------------------------------------------------------------
    # Test: resultMap/selectKey does not crash pipeline
    # -------------------------------------------------------------------------

    def test_resultmap_does_not_crash_pipeline(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict[str, Any],
        validator: ContractValidator,
    ) -> None:
        """
        Verify running full pipeline on resultMap/selectKey scenarios does not crash.

        These are parsed as SQL units but optimization may not apply since
        they are MyBatis-specific tags affecting result mapping, not SQL execution.
        """
        # Run init → parse → recognition → optimize → patch
        stages = ["init", "parse", "recognition", "optimize", "patch"]
        results = {}

        for stage_name in stages:
            result = run_v9_stage(
                stage_name,
                temp_run_dir,
                config=real_mapper_config,
                validator=validator,
            )
            results[stage_name] = result

            # Each stage should succeed (not crash)
            assert result.get("success") is not None, (
                f"Stage {stage_name} returned no success field: {result}"
            )

        # All stages should complete without crashing
        for stage_name, result in results.items():
            assert result.get("success") is True, f"Stage {stage_name} failed: {result}"

    # -------------------------------------------------------------------------
    # Test: resultMap SQL is valid (no malformed SQL)
    # -------------------------------------------------------------------------

    def test_resultmap_sql_is_valid(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify resultMap SQL content is valid SQL (not fragmented or malformed).

        The SQL should be parseable and contain expected keywords.
        """
        branches = load_branches(init_then_parse_dir)

        resultmap_scenarios = [
            "com.test.mapper.UserMapper.testResultMapAssociation",
            "com.test.mapper.UserMapper.testResultMapCollection",
            "com.test.mapper.UserMapper.testNestedResult",
        ]

        for sql_key in resultmap_scenarios:
            unit = find_sql_unit(branches, sql_key)
            if unit is None:
                continue  # Skip if not found

            sql = unit.get("sql", "").upper()

            # Should have SELECT keyword
            assert "SELECT" in sql, f"Expected SELECT in {sql_key}: {sql[:200]}"

            # Should not be just fragment (should have FROM)
            assert "FROM" in sql, f"Expected FROM in {sql_key}: {sql[:200]}"

    # -------------------------------------------------------------------------
    # Test: selectKey SQL contains INSERT
    # -------------------------------------------------------------------------

    def test_selectkey_sql_contains_insert(
        self,
        init_then_parse_dir: Path,
    ) -> None:
        """
        Verify selectKey SQL contains INSERT statement.

        selectKey is used with INSERT statements for key generation.
        """
        branches = load_branches(init_then_parse_dir)

        selectkey_scenarios = [
            "com.test.mapper.UserMapper.testSelectKeyOracle",
            "com.test.mapper.UserMapper.testSelectKeyPostgres",
            "com.test.mapper.UserMapper.testSelectKeyMysql",
            "com.test.mapper.UserMapper.testSelectKeyUuid",
        ]

        for sql_key in selectkey_scenarios:
            unit = find_sql_unit(branches, sql_key)
            if unit is None:
                continue  # Skip if not found

            sql = unit.get("sql", "").upper()

            # Should have INSERT keyword
            assert "INSERT" in sql, f"Expected INSERT in {sql_key}: {sql[:200]}"
