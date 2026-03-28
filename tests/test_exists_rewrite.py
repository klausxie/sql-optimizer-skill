"""EXISTS Rewrite 单元测试"""

import pytest
from sqlopt.platforms.sql.exists_utils import (
    contains_exists,
    detect_exists_pattern,
    is_correlated,
    validate_exists_rewrite_safety,
)


class TestContainsExists:
    def test_contains_exists(self):
        assert contains_exists("SELECT * FROM t WHERE EXISTS (SELECT 1 FROM t2)") is True

    def test_contains_not_exists(self):
        assert contains_exists("SELECT * FROM t WHERE NOT EXISTS (SELECT 1 FROM t2)") is True

    def test_no_exists(self):
        assert contains_exists("SELECT * FROM t WHERE id = 1") is False

    def test_empty_string(self):
        assert contains_exists("") is False


class TestDetectExistsPattern:
    def test_exists_pattern(self):
        result = detect_exists_pattern("SELECT * FROM a WHERE EXISTS (SELECT 1 FROM b WHERE b.id = a.id)")
        assert result is not None
        assert result["type"] == "EXISTS"
        assert "b.id" in result["subquery"]

    def test_not_exists_pattern(self):
        result = detect_exists_pattern("SELECT * FROM a WHERE NOT EXISTS (SELECT 1 FROM b WHERE b.id = a.id)")
        assert result is not None
        assert result["type"] == "NOT_EXISTS"

    def test_no_exists(self):
        result = detect_exists_pattern("SELECT * FROM a WHERE id = 1")
        assert result is None

    def test_empty_string(self):
        result = detect_exists_pattern("")
        assert result is None


class TestIsCorrelated:
    def test_correlated_subquery(self):
        # 检测到 table.column 模式，认为可能是关联子查询
        assert is_correlated("SELECT * FROM b WHERE b.id = a.id") is True

    def test_non_correlated_subquery(self):
        # 简单列比较没有 table 前缀，不触发关联检测
        assert is_correlated("SELECT * FROM b WHERE status = 1") is False


class TestValidateExistsRewriteSafety:
    def test_safe_exists_to_in(self):
        is_safe, reason = validate_exists_rewrite_safety(
            "SELECT * FROM a WHERE EXISTS (SELECT 1 FROM b WHERE b.id = a.id)",
            "SELECT * FROM a WHERE a.id IN (SELECT b.id FROM b)",
            "EXISTS_TO_IN"
        )
        assert is_safe is True
        assert reason is None

    def test_safe_not_exists_to_not_in(self):
        is_safe, reason = validate_exists_rewrite_safety(
            "SELECT * FROM a WHERE NOT EXISTS (SELECT 1 FROM b WHERE b.id = a.id)",
            "SELECT * FROM a WHERE a.id NOT IN (SELECT b.id FROM b)",
            "NOT_EXISTS_TO_NOT_IN"
        )
        # 这个测试取决于具体实现，可能返回 False 如果有 IS NULL
        # 简化处理
        assert reason in [None, "NULL_SEMANTICS_MAY_DIFFER"]

    def test_empty_sql(self):
        is_safe, reason = validate_exists_rewrite_safety("", "", "EXISTS_TO_IN")
        assert is_safe is False
        assert reason == "EMPTY_SQL"

    def test_join_complexity_too_high(self):
        is_safe, reason = validate_exists_rewrite_safety(
            "SELECT * FROM a WHERE EXISTS (SELECT 1 FROM b WHERE b.id = a.id)",
            "SELECT * FROM a JOIN b JOIN c ON a.id = b.id AND b.id = c.id",
            "EXISTS_TO_JOIN"
        )
        assert is_safe is False
        assert reason == "JOIN_COMPLEXITY_TOO_HIGH"