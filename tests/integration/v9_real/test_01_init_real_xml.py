"""
V9 Init Stage Integration Test with Real MyBatis XML Files

Tests the INIT stage using real MyBatis XML files from tests/real/mybatis-test/.
Validates SQL unit extraction, namespace detection, and dynamic tag recognition.
"""

import json
from pathlib import Path
import pytest

from sqlopt.application.v9_stages import run_stage

# Imports from conftest
from conftest import load_sql_units, find_sql_unit, filter_sql_units, selected_scenarios


# =============================================================================
# Test Class: TestV9InitRealXML
# =============================================================================


class TestV9InitRealXML:
    """Integration tests for V9 INIT stage with real MyBatis XML files."""

    def test_init_scans_real_mapper_files(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that INIT stage correctly scans real mapper XML files.

        Validates:
        - init/sql_units.json is created
        - At least 95 SQL units are extracted (UserMapper.xml has 95+ statements)
        - Each unit has required fields: sqlKey, namespace, statementId, statementType
        - sqlKey format is namespace.statementId
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        # Verify stage succeeded
        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units_path = temp_run_dir / "init" / "sql_units.json"
        assert sql_units_path.exists(), f"sql_units.json not found at {sql_units_path}"

        # Verify valid JSON
        sql_units = load_sql_units(temp_run_dir)
        assert isinstance(sql_units, list), "sql_units.json should contain a list"
        assert len(sql_units) > 0, "sql_units.json should not be empty"

        # Verify at least 95 SQL units (UserMapper.xml has 95+ statements)
        assert len(sql_units) >= 95, (
            f"Expected at least 95 SQL units, got {len(sql_units)}"
        )

        # Verify each unit has required fields
        required_fields = ["sqlKey", "namespace", "statementId", "statementType", "sql"]
        for i, unit in enumerate(sql_units):
            assert isinstance(unit, dict), f"Unit {i} is not a dict"
            for field in required_fields:
                assert field in unit, (
                    f"Unit {i} missing required field '{field}': {unit}"
                )

        # Verify sqlKey format is namespace.statementId
        for unit in sql_units:
            sql_key = unit.get("sqlKey", "")
            namespace = unit.get("namespace", "")
            statement_id = unit.get("statementId", "")

            expected_sql_key = f"{namespace}.{statement_id}"
            assert sql_key == expected_sql_key, (
                f"sqlKey mismatch: expected '{expected_sql_key}', got '{sql_key}'"
            )

    def test_init_extracts_correct_namespaces(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that INIT stage correctly extracts all three namespaces:
        - com.test.mapper.UserMapper
        - com.test.mapper.CommonMapper
        - com.test.mapper.OrderMapper
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units = load_sql_units(temp_run_dir)
        assert len(sql_units) > 0, "No SQL units found"

        # Verify UserMapper namespace
        user_mapper_units = [
            u for u in sql_units if u.get("namespace") == "com.test.mapper.UserMapper"
        ]
        assert len(user_mapper_units) > 0, (
            "No units found for com.test.mapper.UserMapper namespace"
        )

        # Verify CommonMapper namespace
        common_mapper_units = [
            u for u in sql_units if u.get("namespace") == "com.test.mapper.CommonMapper"
        ]
        assert len(common_mapper_units) > 0, (
            "No units found for com.test.mapper.CommonMapper namespace"
        )

        # Verify OrderMapper namespace
        order_mapper_units = [
            u for u in sql_units if u.get("namespace") == "com.test.mapper.OrderMapper"
        ]
        assert len(order_mapper_units) > 0, (
            "No units found for com.test.mapper.OrderMapper namespace"
        )

    def test_init_detects_dynamic_tags(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that INIT stage correctly detects dynamic features (if/choose/foreach).

        SQL units with dynamic features like testSingleIf should have
        a dynamicFeatures field populated with tags like ["IF"] or ["IF", "WHERE"].
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units = load_sql_units(temp_run_dir)

        # Find testSingleIf unit
        single_if_unit = find_sql_unit(
            sql_units, "com.test.mapper.UserMapper.testSingleIf"
        )

        if single_if_unit is not None:
            # Verify dynamicFeatures is populated
            assert "dynamicFeatures" in single_if_unit, (
                "testSingleIf unit missing dynamicFeatures field"
            )

            dynamic_features = single_if_unit.get("dynamicFeatures", [])
            # Should detect IF tag for testSingleIf which has <if test="...">
            assert len(dynamic_features) > 0, (
                f"testSingleIf should have dynamic features, got: {dynamic_features}"
            )

        # Find a unit with multiple IF tags
        two_if_unit = find_sql_unit(sql_units, "com.test.mapper.UserMapper.testTwoIf")

        if two_if_unit is not None:
            dynamic_features = two_if_unit.get("dynamicFeatures", [])
            # Should detect multiple IF tags
            if_features = [f for f in dynamic_features if "IF" in f.upper()]
            assert len(if_features) >= 2, (
                f"testTwoIf should have at least 2 IF features, got: {dynamic_features}"
            )

        # Find a unit with foreach
        foreach_units = [
            u
            for u in sql_units
            if "foreach" in u.get("statementId", "").lower()
            or any("FOREACH" in str(f).upper() for f in u.get("dynamicFeatures", []))
        ]

        if len(foreach_units) > 0:
            foreach_unit = foreach_units[0]
            dynamic_features = foreach_unit.get("dynamicFeatures", [])
            assert len(dynamic_features) > 0, (
                f"Foreach unit should have dynamic features, got: {dynamic_features}"
            )

    def test_init_sql_key_uniqueness(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that all sqlKey values are unique within the result.

        Duplicate sqlKeys would indicate a problem with the scanner or
        namespace/statementId extraction logic.
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units = load_sql_units(temp_run_dir)

        # Collect all sqlKeys
        sql_keys = [unit.get("sqlKey") for unit in sql_units]

        # Check for None values
        none_keys = [k for k in sql_keys if k is None]
        assert len(none_keys) == 0, f"Found None sqlKeys: {none_keys}"

        # Check for duplicates
        seen_keys: set[str] = set()
        duplicates: list[str] = []
        for key in sql_keys:
            if key in seen_keys:
                duplicates.append(key)
            seen_keys.add(key)

        assert len(duplicates) == 0, f"Found duplicate sqlKeys: {set(duplicates)}"

        # Verify total count matches
        assert len(sql_keys) == len(sql_units), (
            "sqlKeys count should match sql_units count"
        )

    def test_init_sql_content_not_empty(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that all SQL units have non-empty sql content.

        Each SQL unit should have actual SQL text, not just metadata.
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units = load_sql_units(temp_run_dir)

        for i, unit in enumerate(sql_units):
            sql = unit.get("sql", "")
            assert sql and len(sql.strip()) > 0, (
                f"Unit {i} has empty or whitespace-only sql: {unit.get('sqlKey')}"
            )

    def test_init_statement_types_valid(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that all extracted SQL units have valid statementType values.

        Valid MyBatis statement types include: SELECT, INSERT, UPDATE, DELETE, etc.
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        assert result.get("success", False), f"Init stage failed: {result}"

        # Load sql_units.json
        sql_units = load_sql_units(temp_run_dir)

        valid_statement_types = {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "REPLACE",
            "CALL",
            "EXEC",
            "EXECUTE",
        }

        for i, unit in enumerate(sql_units):
            statement_type = unit.get("statementType", "")
            assert statement_type in valid_statement_types, (
                f"Unit {i} ({unit.get('sqlKey')}) has invalid statementType: "
                f"'{statement_type}'. Expected one of: {valid_statement_types}"
            )
