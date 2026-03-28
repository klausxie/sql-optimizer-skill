"""Unit tests for BranchValidator."""

from __future__ import annotations

import pytest

from sqlopt.stages.branching.branch_validator import BranchValidator


class TestBranchValidatorValidateSql:
    """Tests for validate_sql static method."""

    def test_valid_select(self):
        assert BranchValidator.validate_sql("SELECT * FROM users")

    def test_valid_select_with_where(self):
        assert BranchValidator.validate_sql("SELECT * FROM users WHERE id = 1")

    def test_valid_update_with_set_and_where(self):
        assert BranchValidator.validate_sql("UPDATE users SET name = 'a' WHERE id = 1")

    def test_valid_delete_with_where(self):
        assert BranchValidator.validate_sql("DELETE FROM users WHERE id = 1")

    def test_valid_insert(self):
        assert BranchValidator.validate_sql("INSERT INTO users (name) VALUES ('a')")

    def test_invalid_update_missing_set(self):
        assert not BranchValidator.validate_sql("UPDATE users WHERE id = 1")

    def test_invalid_update_missing_where(self):
        assert not BranchValidator.validate_sql("UPDATE users SET name = 'a'")

    def test_delete_without_where_is_syntactically_valid(self):
        assert BranchValidator.validate_sql("DELETE FROM users")

    def test_invalid_insert_missing_values(self):
        assert not BranchValidator.validate_sql("INSERT INTO users (name)")

    def test_invalid_select_missing_from(self):
        assert not BranchValidator.validate_sql("SELECT * WHERE id = 1")


class TestValidateAndDeduplicate:
    """Tests for validate_and_deduplicate method."""

    def test_baseline_always_first(self):
        """All-false branch must be first in output."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users WHERE name = #{name}",
                "active_conditions": ["name != null"],
                "risk_score": 5.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users",
                "active_conditions": [],
                "risk_score": 0.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 2
        assert result.branches[0]["active_conditions"] == []
        assert result.branches[1]["active_conditions"] == ["name != null"]

    def test_risk_priority_ordering(self):
        """Higher risk_score branches come before lower ones."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users",
                "active_conditions": [],
                "risk_score": 0.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "active_conditions": ["status != null"],
                "risk_score": 2.0,
            },
            {
                "branch_id": 2,
                "sql": "SELECT * FROM users WHERE name LIKE #{name}",
                "active_conditions": ["name != null"],
                "risk_score": 10.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 3
        assert result.branches[0]["active_conditions"] == []
        assert result.branches[1]["active_conditions"] == ["name != null"]
        assert result.branches[2]["active_conditions"] == ["status != null"]

    def test_max_branches_hard_truncate(self):
        """Output respects max_branches limit."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": i,
                "sql": f"SELECT * FROM users WHERE id = {i}",
                "active_conditions": [f"cond_{i} != null"],
                "risk_score": float(i),
            }
            for i in range(20)
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=5)

        assert len(result.branches) == 5

    def test_duplicates_removed_by_sql_content(self):
        """Same SQL content keeps only highest-risk branch."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "active_conditions": ["status != null"],
                "risk_score": 2.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "active_conditions": ["status != null"],
                "risk_score": 5.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 1
        assert result.branches[0]["risk_score"] == 5.0

    def test_empty_sql_ignored(self):
        """Branches with empty SQL are filtered out."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "",
                "active_conditions": [],
                "risk_score": 0.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users",
                "active_conditions": [],
                "risk_score": 0.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 1
        assert result.branches[0]["sql"] == "SELECT * FROM users"

    def test_empty_in_clause_filtered(self):
        """IN () or NOT IN () clauses are filtered out."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users WHERE id IN ()",
                "active_conditions": ["ids != null"],
                "risk_score": 5.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users WHERE id IN (1, 2, 3)",
                "active_conditions": ["ids != null"],
                "risk_score": 5.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 1
        assert "IN ()" not in result.branches[0]["sql"].upper()

    def test_branch_id_reassigned(self):
        """Branch IDs are renumbered sequentially from 0."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 99,
                "sql": "SELECT * FROM users WHERE a = #{a}",
                "active_conditions": ["a != null"],
                "risk_score": 1.0,
            },
            {
                "branch_id": 88,
                "sql": "SELECT * FROM users WHERE b = #{b}",
                "active_conditions": ["b != null"],
                "risk_score": 2.0,
            },
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert result.branches[0]["branch_id"] == 0
        assert result.branches[1]["branch_id"] == 1

    def test_baseline_occupies_first_slot(self):
        """Baseline counts toward max_branches."""
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users",
                "active_conditions": [],
                "risk_score": 0.0,
            },
        ] + [
            {
                "branch_id": i,
                "sql": f"SELECT * FROM users WHERE id = {i}",
                "active_conditions": [f"cond_{i} != null"],
                "risk_score": float(i + 1),
            }
            for i in range(1, 10)
        ]
        result = validator.validate_and_deduplicate(branches, max_branches=5)

        assert len(result.branches) == 5
        assert result.branches[0]["active_conditions"] == []


class TestContainsEmptyInClause:
    """Tests for _contains_empty_in_clause helper."""

    def test_empty_in_parens(self):
        assert BranchValidator._contains_empty_in_clause("SELECT * FROM users WHERE id IN ()")

    def test_not_empty_in_with_values(self):
        assert not BranchValidator._contains_empty_in_clause("SELECT * FROM users WHERE id IN (1, 2)")

    def test_not_in_clause(self):
        assert not BranchValidator._contains_empty_in_clause("SELECT * FROM users WHERE id = 1")

    def test_not_in_with_space(self):
        assert BranchValidator._contains_empty_in_clause("SELECT * FROM users WHERE id IN (  )")
