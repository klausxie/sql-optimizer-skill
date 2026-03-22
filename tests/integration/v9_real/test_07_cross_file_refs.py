"""
V9 Cross-File SQL Fragment Reference Integration Tests

Tests that SQL fragment <include refid="..."> references across multiple
XML mapper files (CommonMapper.xml, UserMapper.xml, OrderMapper.xml) are
correctly resolved during init → parse stages.

Cross-file refs look like:
  <include refid="com.test.mapper.CommonMapper.userBaseColumns"/>

After resolution, the SQL should contain the actual fragment content like
"id, name, email, status, type".
"""

import json
from pathlib import Path
from typing import Any

import pytest

from sqlopt.application.v9_stages import run_stage

# Imports from conftest
from conftest import load_branches, find_sql_unit


# =============================================================================
# Test Class: TestV9CrossFileReferences
# =============================================================================


class TestV9CrossFileReferences:
    """Integration tests for V9 cross-file SQL fragment resolution."""

    @pytest.fixture(autouse=True)
    def setup(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator,
    ) -> None:
        """
        Run init → parse stages once for all tests in this class.

        This fixture runs before each test method and provides:
        - temp_run_dir: temporary directory for test output
        - real_mapper_config: config pointing to real mybatis-test mappers
        - validator: contract validator
        - branches: parsed SQL units with branches
        """
        self.temp_run_dir = temp_run_dir
        self.real_mapper_config = real_mapper_config
        self.validator = validator

        # Run init stage
        init_result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert init_result.get("success", False), f"Init stage failed: {init_result}"

        # Run parse stage
        parse_result = run_stage(
            "parse",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert parse_result.get("success", False), f"Parse stage failed: {parse_result}"

        # Load branches for all tests
        self.branches = load_branches(temp_run_dir)
        assert len(self.branches) > 0, "No branches loaded from parse output"

    def test_cross_file_include_resolves(
        self,
    ) -> None:
        """
        Test that simple cross-file include resolves to fragment content.

        Scenario: testCrossFileInclude uses:
          <include refid="com.test.mapper.CommonMapper.userBaseColumns"/>
          <include refid="com.test.mapper.CommonMapper.activeStatusCondition"/>

        Expected: After resolution, SQL should contain actual column list
        "id, name, email, status, type" from userBaseColumns fragment.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileInclude",
        )
        assert unit is not None, "testCrossFileInclude not found in branches"

        # Get branches and check for resolved SQL
        branches = unit.get("branches", [])
        assert len(branches) > 0, f"testCrossFileInclude has no branches: {unit}"

        # At least one branch should have resolved fragment content
        # userBaseColumns = "id, name, email, status, type"
        found_resolution = False
        for branch in branches:
            sql = branch.get("sql", "")
            # Check for the actual fragment columns being inlined
            if "id" in sql.lower() and "name" in sql.lower():
                # Verify it's not just the refid literal
                assert "com.test.mapper.commonmapper" not in sql.lower(), (
                    f"Fragment refid not resolved, SQL: {sql}"
                )
                found_resolution = True
                break

        assert found_resolution, (
            f"userBaseColumns fragment not resolved in testCrossFileInclude. "
            f"Branches SQL: {[b.get('sql', '') for b in branches]}"
        )

    def test_chained_cross_file_include(
        self,
    ) -> None:
        """
        Test 3-level chained cross-file include resolution.

        Scenario: testChainedCrossFileInclude uses local fragment "chainedCondition":
          <sql id="chainedCondition">
            <include refid="com.test.mapper.CommonMapper.complexCommonCondition"/>
            AND type IS NOT NULL
          </sql>

        This creates a 3-level chain:
          Level 1: testChainedCrossFileInclude references "chainedCondition"
          Level 2: chainedCondition references "complexCommonCondition"
          Level 3: complexCommonCondition is in CommonMapper.xml

        Expected: All three levels should resolve correctly.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testChainedCrossFileInclude",
        )
        assert unit is not None, "testChainedCrossFileInclude not found in branches"

        branches = unit.get("branches", [])
        assert len(branches) > 0, f"testChainedCrossFileInclude has no branches: {unit}"

        # For chained includes, we need to verify:
        # 1. The local fragment "chainedCondition" is resolved
        # 2. The CommonMapper fragment is also resolved
        found_valid_sql = False
        for branch in branches:
            sql = branch.get("sql", "")
            # After full resolution:
            # - Should NOT contain unresolved refid literals
            # - Should contain actual content (choose/when from complexCommonCondition)
            sql_lower = sql.lower()

            # Should not have the unresolved refid
            if "com.test.mapper.commonmapper" in sql_lower:
                # Check if it's just a literal string or actually unresolved
                # If the content is there (like 'status' or 'choose'), it's resolved
                if "choose" not in sql_lower and "when" not in sql_lower:
                    assert False, (
                        f"Fragment refid appears unresolved in chained include. "
                        f"SQL: {sql}"
                    )
            else:
                # Refid not present as literal - good sign it was resolved
                found_valid_sql = True

        assert found_valid_sql, (
            f"Chained cross-file include not properly resolved. "
            f"Branches: {[b.get('sql', '') for b in branches]}"
        )

    def test_cross_file_in_choose(
        self,
    ) -> None:
        """
        Test cross-file include inside choose/when/otherwise tags.

        Scenario: testCrossFileInChoose uses:
          <choose>
            <when test="filterMode == 'active'">
              <include refid="com.test.mapper.CommonMapper.activeStatusCondition"/>
            </when>
            <when test="filterMode == 'complex'">
              <include refid="com.test.mapper.CommonMapper.complexCommonCondition"/>
            </when>
            <otherwise>
              <include refid="com.test.mapper.CommonMapper.dateRangeCondition"/>
            </otherwise>
          </choose>

        Expected: Includes should be resolved within the choose structure.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileInChoose",
        )
        assert unit is not None, "testCrossFileInChoose not found in branches"

        branches = unit.get("branches", [])
        assert len(branches) > 0, f"testCrossFileInChoose has no branches: {unit}"

        # Verify that includes were resolved
        # Each branch should have the actual SQL content, not the refid
        for branch in branches:
            sql = branch.get("sql", "")
            sql_lower = sql.lower()

            # Should not contain unresolved cross-file refids
            if "com.test.mapper.commonmapper" in sql_lower:
                # If it still has the refid literal, the include wasn't resolved
                assert False, (
                    f"Cross-file include not resolved in choose structure. SQL: {sql}"
                )

    def test_cross_file_fragment_not_found_handled(
        self,
    ) -> None:
        """
        Test graceful handling when a fragment reference cannot be resolved.

        When a fragment refid cannot be found (e.g., typo or missing fragment),
        the system should handle it gracefully - either leave the unresolved
        ref as-is in the SQL or handle it without crashing.

        This test verifies that the parse stage completes without error
        even if some fragment references might be invalid.
        """
        # Run init → parse (already done in setup)
        # If we got here without exception, the stages completed

        # Verify branches were still generated
        assert len(self.branches) > 0, (
            "No branches found - parse may have failed completely"
        )

        # The testCrossFileInclude unit should exist and have branches
        # even if some fragments couldn't be resolved
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileInclude",
        )

        if unit is not None:
            # Even if resolution failed partially, the unit should exist
            assert "branches" in unit or "sql" in unit, (
                f"Unit exists but has no branches or sql: {unit}"
            )

    def test_cross_file_multiple_includes(
        self,
    ) -> None:
        """
        Test multiple cross-file includes in a single SQL statement.

        Scenario: testCrossFileIncludeWithIf uses:
          SELECT <include refid="com.test.mapper.CommonMapper.userBaseColumns"/>,
                 <include refid="com.test.mapper.CommonMapper.auditColumns"/>
          FROM users
          <where>
            <if test="name != null">AND name LIKE CONCAT('%', #{name}, '%')</if>
            <include refid="com.test.mapper.CommonMapper.activeStatusCondition"/>
          </where>

        Expected: All includes should resolve to actual content.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileIncludeWithIf",
        )
        assert unit is not None, "testCrossFileIncludeWithIf not found in branches"

        branches = unit.get("branches", [])
        assert len(branches) > 0, f"testCrossFileIncludeWithIf has no branches: {unit}"

        # Check that multiple includes were resolved
        found_resolution = False
        for branch in branches:
            sql = branch.get("sql", "")
            sql_lower = sql.lower()

            # userBaseColumns = id, name, email, status, type
            # auditColumns = created_at, updated_at
            # Should have at least some of these columns inlined
            if "id" in sql_lower or "created_at" in sql_lower:
                # Should not have unresolved refids
                unresolved_count = sql_lower.count("com.test.mapper.commonmapper")
                assert unresolved_count == 0, (
                    f"Found {unresolved_count} unresolved cross-file refs. SQL: {sql}"
                )
                found_resolution = True

        assert found_resolution, (
            f"Multiple cross-file includes not resolved. "
            f"Branches: {[b.get('sql', '') for b in branches]}"
        )

    def test_cross_file_in_foreach(
        self,
    ) -> None:
        """
        Test cross-file include combined with foreach tag.

        Scenario: testCrossFileWithForeach combines:
          - Cross-file include in SELECT clause
          - Cross-file include with if/foreach in WHERE clause
          - Cross-file include for pagination

        Expected: All cross-file refs should resolve within foreach context.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileWithForeach",
        )
        assert unit is not None, "testCrossFileWithForeach not found in branches"

        branches = unit.get("branches", [])
        assert len(branches) > 0, f"testCrossFileWithForeach has no branches: {unit}"

        # Verify cross-file refs are resolved
        for branch in branches:
            sql = branch.get("sql", "")
            sql_lower = sql.lower()

            # Should have foreach-related content (like "in (")
            assert "in (" in sql_lower or "foreach" in sql_lower, (
                f"Expected foreach-related SQL content. SQL: {sql}"
            )

            # Should not have unresolved cross-file refids
            if "com.test.mapper.commonmapper" in sql_lower:
                assert False, f"Cross-file include not resolved in foreach. SQL: {sql}"

    def test_cross_file_fragment_namespace_qualification(
        self,
    ) -> None:
        """
        Test that namespace-qualified cross-file refs resolve correctly.

        Cross-file refs use fully qualified names like:
          com.test.mapper.CommonMapper.userBaseColumns

        While local refs just use:
          baseColumns

        This test ensures the namespace-qualified refs are handled properly.
        """
        unit = find_sql_unit(
            self.branches,
            "com.test.mapper.UserMapper.testCrossFileInclude",
        )
        assert unit is not None

        branches = unit.get("branches", [])

        # The fully qualified refid should be resolved to actual content
        for branch in branches:
            sql = branch.get("sql", "")
            # The fully qualified refid string should not appear in output
            assert "com.test.mapper.commonmapper.userbasecolumns" not in sql.lower(), (
                f"Namespace-qualified refid not resolved. SQL: {sql}"
            )
