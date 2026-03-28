"""JOIN 消除单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import (
    get_select_columns,
    is_join_table_used,
    join_elimination_candidate,
)


class TestGetSelectColumns:
    def test_simple_columns(self):
        sql = "SELECT id, name FROM users"
        result = get_select_columns(sql)
        assert "id" in result
        assert "name" in result

    def test_star_select(self):
        sql = "SELECT * FROM users"
        result = get_select_columns(sql)
        assert result == ['*']

    def test_qualified_columns(self):
        sql = "SELECT u.id, u.name FROM users u"
        result = get_select_columns(sql)
        assert "id" in result
        assert "name" in result


class TestIsJoinTableUsed:
    def test_table_in_select(self):
        sql = "SELECT u.id, u.name FROM users u JOIN orders o ON u.id = o.user_id"
        assert is_join_table_used(sql, "o") is True

    def test_table_not_used(self):
        sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        assert is_join_table_used(sql, "o") is False


class TestJoinEliminationCandidate:
    def test_candidate_found(self):
        sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        result = join_elimination_candidate(sql)
        assert result is not None
        assert result["table"] == "o"
        assert result["reason"] == "UNUSED_TABLE"

    def test_no_candidate(self):
        sql = "SELECT u.id, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        result = join_elimination_candidate(sql)
        assert result is None

    def test_no_join(self):
        sql = "SELECT id FROM users WHERE id = 1"
        result = join_elimination_candidate(sql)
        assert result is None