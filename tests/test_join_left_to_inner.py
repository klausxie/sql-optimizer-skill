"""LEFT→INNER JOIN 转换单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import (
    contains_join,
    detect_join_type,
    extract_join_tables,
    has_not_null_condition,
    left_to_inner_rewrite,
    JoinType,
)


class TestContainsJoin:
    def test_contains_left_join(self):
        assert contains_join("SELECT * FROM a LEFT JOIN b ON a.id = b.id") is True

    def test_contains_inner_join(self):
        assert contains_join("SELECT * FROM a INNER JOIN b ON a.id = b.id") is True

    def test_contains_no_join(self):
        assert contains_join("SELECT * FROM a WHERE id = 1") is False


class TestDetectJoinType:
    def test_detect_left_join(self):
        result = detect_join_type("SELECT * FROM a LEFT JOIN b ON a.id = b.id")
        assert result == JoinType.LEFT

    def test_detect_inner_join(self):
        result = detect_join_type("SELECT * FROM a INNER JOIN b ON a.id = b.id")
        assert result == JoinType.INNER

    def test_detect_right_join(self):
        result = detect_join_type("SELECT * FROM a RIGHT JOIN b ON a.id = b.id")
        assert result == JoinType.RIGHT

    def test_detect_no_join(self):
        result = detect_join_type("SELECT * FROM a WHERE id = 1")
        assert result is None


class TestExtractJoinTables:
    def test_extract_single_join(self):
        result = extract_join_tables("SELECT * FROM a LEFT JOIN b ON a.id = b.id")
        assert "b" in result

    def test_extract_multiple_joins(self):
        result = extract_join_tables("SELECT * FROM a LEFT JOIN b ON a.id = b.id LEFT JOIN c ON a.id = c.id")
        assert "b" in result
        assert "c" in result


class TestHasNotNullCondition:
    def test_has_is_not_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id IS NOT NULL"
        assert has_not_null_condition(sql, "b") is True

    def test_has_not_equals_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id != NULL"
        assert has_not_null_condition(sql, "b") is True

    def test_no_not_null_condition(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.status = 1"
        assert has_not_null_condition(sql, "b") is False


class TestLeftToInnerRewrite:
    def test_rewrite_left_to_inner(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id IS NOT NULL"
        result = left_to_inner_rewrite(sql)
        assert result is not None
        assert "INNER JOIN" in result
        assert "LEFT JOIN" not in result

    def test_no_rewrite_without_not_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.status = 1"
        result = left_to_inner_rewrite(sql)
        assert result is None

    def test_no_rewrite_inner_join(self):
        sql = "SELECT * FROM a INNER JOIN b ON a.id = b.id"
        result = left_to_inner_rewrite(sql)
        assert result is None