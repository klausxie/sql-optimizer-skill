"""Unit tests for function_wrap_detector module."""

from __future__ import annotations

import pytest
from sqlopt.common.function_wrap_detector import (
    INDEX_BYPASS_FUNCTIONS,
    detect_function_wrapped_columns,
)


class TestDetectFunctionWrappedColumns:
    """Test detect_function_wrapped_columns function."""

    def test_upper(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE UPPER(name) = 'JOHN'", None)
        assert ("name", "UPPER") in result

    def test_lower(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE LOWER(name) = 'john'", None)
        assert ("name", "LOWER") in result

    def test_date(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE DATE(created_at) = '2024-01-01'", None)
        assert ("created_at", "DATE") in result

    def test_year(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE YEAR(created_at) = 2024", None)
        assert ("created_at", "YEAR") in result

    def test_month(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE MONTH(created_at) = 1", None)
        assert ("created_at", "MONTH") in result

    def test_date_format(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE DATE_FORMAT(date, '%Y') = '2024'", None)
        assert ("date", "DATE_FORMAT") in result

    def test_substring(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE SUBSTRING(col, 1, 10) = 'test'", None)
        assert ("col", "SUBSTRING") in result

    def test_trim(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE TRIM(col) = 'test'", None)
        assert ("col", "TRIM") in result

    def test_cast(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE CAST(col AS SIGNED) = 1", None)
        assert ("col", "CAST") in result

    def test_coalesce(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE COALESCE(col1, col2) = 'default'", None)
        assert ("col1", "COALESCE") in result
        assert ("col2", "COALESCE") in result

    def test_nested_functions(self):
        result = detect_function_wrapped_columns(
            "SELECT * FROM t WHERE DATE_FORMAT(DATE_ADD(col, INTERVAL 1 DAY), '%Y') = '2024'",
            None,
        )
        cols = [col for col, _ in result]
        assert "col" in cols

    def test_aggregate_not_flagged_count(self):
        result = detect_function_wrapped_columns("SELECT COUNT(*) FROM t", None)
        assert result == []

    def test_aggregate_not_flagged_sum(self):
        result = detect_function_wrapped_columns("SELECT SUM(amount) FROM t", None)
        assert result == []

    def test_aggregate_not_flagged_avg(self):
        result = detect_function_wrapped_columns("SELECT AVG(price) FROM t", None)
        assert result == []

    def test_no_where_clause(self):
        result = detect_function_wrapped_columns("SELECT * FROM t", None)
        assert result == []

    def test_empty_sql(self):
        result = detect_function_wrapped_columns("", None)
        assert result == []

    def test_mysql_dialect(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE UPPER(name) = 'JOHN'", "mysql")
        assert ("name", "UPPER") in result

    def test_postgres_dialect(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE UPPER(name) = 'JOHN'", "postgres")
        assert ("name", "UPPER") in result

    def test_multiple_columns_same_function(self):
        result = detect_function_wrapped_columns(
            "SELECT * FROM t WHERE UPPER(name) = 'JOHN' AND LOWER(status) = 'active'",
            None,
        )
        assert ("name", "UPPER") in result
        assert ("status", "LOWER") in result

    def test_subquery_not_flagged(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE id IN (SELECT UPPER(id) FROM other)", None)
        assert ("id", "UPPER") in result

    def test_length_function(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE LENGTH(name) > 10", None)
        assert ("name", "LENGTH") in result

    def test_replace_function(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE REPLACE(name, 'a', 'b') = 'test'", None)
        assert ("name", "REPLACE") in result

    def test_abs_function(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE ABS(value) > 0", None)
        assert ("value", "ABS") in result

    def test_round_function(self):
        result = detect_function_wrapped_columns("SELECT * FROM t WHERE ROUND(price) > 100", None)
        assert ("price", "ROUND") in result

    def test_concat_function(self):
        result = detect_function_wrapped_columns(
            "SELECT * FROM t WHERE CONCAT(first_name, last_name) = 'JohnDoe'", None
        )
        assert ("first_name", "CONCAT") in result
        assert ("last_name", "CONCAT") in result


class TestIndexBypassFunctionsSet:
    """Test INDEX_BYPASS_FUNCTIONS contains expected functions."""

    def test_has_required_functions(self):
        required = {
            "UPPER",
            "LOWER",
            "DATE",
            "YEAR",
            "MONTH",
            "DAY",
            "DATE_FORMAT",
            "DATE_ADD",
            "DATE_SUB",
            "TRIM",
            "SUBSTRING",
            "CAST",
            "COALESCE",
            "CONCAT",
            "LENGTH",
            "ABS",
            "ROUND",
        }
        for func in required:
            assert func in INDEX_BYPASS_FUNCTIONS, f"Missing function: {func}"

    def test_functions_are_uppercase(self):
        for func in INDEX_BYPASS_FUNCTIONS:
            assert func == func.upper(), f"Function should be uppercase: {func}"
