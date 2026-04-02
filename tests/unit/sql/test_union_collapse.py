"""UNION Collapse 单元测试"""

import pytest
from sqlopt.platforms.sql.union_utils import (
    contains_union,
    detect_union_type,
    validate_union_safety,
    has_nested_union,
    is_union_wrapper_pattern,
)


class TestContainsUnion:
    def test_contains_union_all(self):
        assert contains_union("SELECT * FROM t1 UNION ALL SELECT * FROM t2") is True

    def test_contains_union(self):
        assert contains_union("SELECT * FROM t1 UNION SELECT * FROM t2") is True

    def test_no_union(self):
        assert contains_union("SELECT * FROM t1") is False

    def test_empty_string(self):
        assert contains_union("") is False

    def test_none(self):
        assert contains_union(None) is False


class TestDetectUnionType:
    def test_union_all(self):
        assert detect_union_type("SELECT * FROM t1 UNION ALL SELECT * FROM t2") == "UNION ALL"

    def test_union(self):
        assert detect_union_type("SELECT * FROM t1 UNION SELECT * FROM t2") == "UNION"

    def test_no_union(self):
        assert detect_union_type("SELECT * FROM t1") == "NONE"

    def test_empty(self):
        assert detect_union_type("") == "NONE"


class TestValidateUnionSafety:
    def test_safe_union_all(self):
        is_safe, reason = validate_union_safety("SELECT a FROM t1 UNION ALL SELECT b FROM t2")
        assert is_safe is True
        assert reason is None

    def test_safe_union(self):
        is_safe, reason = validate_union_safety("SELECT a FROM t1 UNION SELECT b FROM t2")
        assert is_safe is True
        assert reason is None

    def test_nested_union_unsafe(self):
        sql = "SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "NESTED_UNION_NOT_SUPPORTED"

    def test_for_update_unsafe(self):
        sql = "SELECT * FROM t1 UNION ALL SELECT * FROM t2 FOR UPDATE"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "FOR_UPDATE_NOT_SUPPORTED"

    def test_distinct_unsafe(self):
        sql = "SELECT DISTINCT a FROM t1 UNION ALL SELECT b FROM t2"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "DISTINCT_SEMANTICS_MAY_DIFFER"


class TestHasNestedUnion:
    def test_single_union(self):
        assert has_nested_union("SELECT a FROM t1 UNION SELECT b FROM t2") is False

    def test_nested_union(self):
        assert has_nested_union("SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3") is True

    def test_union_all_count_once(self):
        # UNION ALL should not be counted as nested
        assert has_nested_union("SELECT a FROM t1 UNION ALL SELECT b FROM t2") is False


class TestIsUnionWrapperPattern:
    def test_wrapper_pattern(self):
        sql = "SELECT * FROM (SELECT a FROM t1 UNION ALL SELECT b FROM t2) tmp"
        assert is_union_wrapper_pattern(sql) is True

    def test_non_wrapper(self):
        sql = "SELECT a FROM t1 UNION ALL SELECT b FROM t2"
        assert is_union_wrapper_pattern(sql) is False

    def test_empty(self):
        assert is_union_wrapper_pattern("") is False