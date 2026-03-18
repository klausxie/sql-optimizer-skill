"""Unit tests for baseline module."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch, MagicMock

from sqlopt.stages.baseline.performance_collector import (
    _get_sql_connect,
    _parse_dsn,
    _substitute_bind_params,
    _calculate_p95,
    collect_performance,
)
from sqlopt.stages.baseline.parameter_parser import parse_parameters
from sqlopt.stages.baseline.parameter_binder import (
    bind_parameters,
    _camel_to_snake,
    _snake_to_camel,
    _find_matching_column,
    _generate_fallback_value,
)
from sqlopt.stages.baseline.data_generator import generate_test_value, generate_row


class TestPerformanceCollector(unittest.TestCase):
    """Tests for performance_collector module."""

    def test_get_sql_connect_returns_driver_when_available(self) -> None:
        """Test that _get_sql_connect returns a driver when available."""
        driver, name = _get_sql_connect()
        # Just verify we get a connection function
        self.assertIsNotNone(driver)

    def test_parse_dsn_parses_mysql_correctly(self) -> None:
        """Test that _parse_dsn correctly parses MySQL DSN."""
        dsn = "mysql://user:password@localhost:3306/testdb"
        result = _parse_dsn(dsn)

        self.assertEqual(result["user"], "user")
        self.assertEqual(result["password"], "password")
        self.assertEqual(result["host"], "localhost")
        self.assertEqual(result["port"], 3306)
        self.assertEqual(result["database"], "testdb")

    def test_parse_dsn_returns_empty_for_invalid_dsn(self) -> None:
        """Test that _parse_dsn returns empty dict for invalid DSN."""
        dsn = "invalid_dsn"
        result = _parse_dsn(dsn)
        self.assertEqual(result, {})

    def test_parse_dsn_returns_empty_for_postgresql(self) -> None:
        """Test that _parse_dsn returns empty dict for PostgreSQL DSN."""
        dsn = "postgresql://user:password@localhost:5432/testdb"
        result = _parse_dsn(dsn)
        self.assertEqual(result, {})

    def test_substitute_bind_params_with_string(self) -> None:
        """Test replacing #{} with string values."""
        sql = "SELECT * FROM users WHERE name = #{name}"
        params = {"name": "Alice"}
        result = _substitute_bind_params(sql, params)
        self.assertEqual(result, "SELECT * FROM users WHERE name = 'Alice'")

    def test_substitute_bind_params_with_number(self) -> None:
        """Test replacing #{} with numeric values."""
        sql = "SELECT * FROM users WHERE age = #{age} AND score = #{score}"
        params = {"age": 25, "score": 95.5}
        result = _substitute_bind_params(sql, params)
        self.assertIn("age = 25", result)
        self.assertIn("score = 95.5", result)

    def test_substitute_bind_params_with_none(self) -> None:
        """Test replacing #{} with None values."""
        sql = "SELECT * FROM users WHERE name = #{name}"
        params = {"name": None}
        result = _substitute_bind_params(sql, params)
        self.assertIn("name = NULL", result)

    def test_substitute_bind_params_with_bool(self) -> None:
        """Test replacing #{} with boolean values."""
        sql = "SELECT * FROM users WHERE active = #{active}"
        params = {"active": True}
        result = _substitute_bind_params(sql, params)
        self.assertIn("active = true", result)

    def test_substitute_bind_params_escapes_quotes(self) -> None:
        """Test that single quotes are escaped properly."""
        sql = "SELECT * FROM users WHERE name = #{name}"
        params = {"name": "O'Brien"}
        result = _substitute_bind_params(sql, params)
        self.assertIn("'O''Brien'", result)

    def test_substitute_bind_params_missing_param(self) -> None:
        """Test that missing parameters are replaced with NULL."""
        sql = "SELECT * FROM users WHERE name = #{name} AND age = #{age}"
        params = {"name": "Alice"}
        result = _substitute_bind_params(sql, params)
        self.assertIn("name = 'Alice'", result)
        self.assertIn("age = NULL", result)

    def test_calculate_p95_with_values(self) -> None:
        """Test calculating 95th percentile."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = _calculate_p95(values)
        # index = int(10 * 0.95) = 9, so value at index 9 = 10.0
        self.assertEqual(result, 10.0)

    def test_calculate_p95_empty_list(self) -> None:
        """Test calculating 95th percentile with empty list."""
        result = _calculate_p95([])
        self.assertEqual(result, 0.0)

    def test_calculate_p95_single_value(self) -> None:
        """Test calculating 95th percentile with single value."""
        result = _calculate_p95([5.0])
        self.assertEqual(result, 5.0)

    def test_collect_performance_raises_without_dsn(self) -> None:
        """Test that collect_performance raises ValueError without DSN."""
        config = {}
        sql = "SELECT 1"

        with self.assertRaises(ValueError) as cm:
            collect_performance(config, sql, {})
        self.assertIn("db.dsn not set", str(cm.exception))


class TestParameterParser(unittest.TestCase):
    """Tests for parameter_parser module."""

    def test_parse_parameters_with_bind_params(self) -> None:
        """Test parsing #{param} style parameters."""
        sql = "SELECT * FROM users WHERE id = #{userId} AND name = #{userName}"
        result = parse_parameters(sql)

        self.assertEqual(len(result), 2)
        param_names = [p["name"] for p in result]
        self.assertIn("userId", param_names)
        self.assertIn("userName", param_names)
        for p in result:
            self.assertEqual(p["type"], "bind")

    def test_parse_parameters_with_literal_params(self) -> None:
        """Test parsing ${param} style parameters."""
        sql = "SELECT * FROM ${tableName} WHERE ${column} = #{value}"
        result = parse_parameters(sql)

        # Should find both literal and bind params
        self.assertGreaterEqual(len(result), 2)
        # Check for literal params (tableName, column) and bind params (value)
        param_types = [p["type"] for p in result]
        self.assertIn("literal", param_types)
        self.assertIn("bind", param_types)

    def test_parse_parameters_with_mixed_params(self) -> None:
        """Test parsing both #{...} and ${...} parameters."""
        sql = "SELECT ${columns} FROM users WHERE id = #{userId}"
        result = parse_parameters(sql)

        self.assertEqual(len(result), 2)

        bind_params = [p for p in result if p["type"] == "bind"]
        literal_params = [p for p in result if p["type"] == "literal"]

        self.assertEqual(len(bind_params), 1)
        self.assertEqual(bind_params[0]["name"], "userId")

        self.assertEqual(len(literal_params), 1)
        self.assertEqual(literal_params[0]["name"], "columns")

    def test_parse_parameters_empty_sql(self) -> None:
        """Test parsing empty SQL returns empty list."""
        result = parse_parameters("")
        self.assertEqual(result, [])

    def test_parse_parameters_no_params(self) -> None:
        """Test parsing SQL without parameters returns empty list."""
        result = parse_parameters("SELECT * FROM users")
        self.assertEqual(result, [])

    def test_parse_parameters_with_complex_expressions(self) -> None:
        """Test parsing parameters with complex expressions inside #{}."""
        sql = "SELECT * FROM users WHERE id = #{user.id} AND name IN (#{names[0]}, #{names[1]})"
        result = parse_parameters(sql)

        self.assertEqual(len(result), 3)
        param_names = [p["name"] for p in result]
        self.assertIn("user.id", param_names)
        self.assertIn("names[0]", param_names)
        self.assertIn("names[1]", param_names)


class TestParameterBinder(unittest.TestCase):
    """Tests for parameter_binder module."""

    def test_camel_to_snake(self) -> None:
        """Test camelCase to snake_case conversion."""
        from sqlopt.stages.baseline.parameter_binder import _camel_to_snake

        # Test standard camelCase
        self.assertEqual(_camel_to_snake("userName"), "user_name")
        self.assertEqual(_camel_to_snake("userID"), "user_id")
        # Single word - all lowercase
        self.assertEqual(_camel_to_snake("ID"), "id")

    def test_snake_to_camel(self) -> None:
        """Test converting snake_case to camelCase."""
        self.assertEqual(_snake_to_camel("user_id"), "userId")
        self.assertEqual(_snake_to_camel("my_user_name"), "myUserName")

    def test_find_matching_column_exact_match(self) -> None:
        """Test finding exact column match."""
        data_row = {"userId": 123, "name": "Alice"}
        result = _find_matching_column("userId", data_row)
        self.assertEqual(result, 123)

    def test_find_matching_column_camel_snake(self) -> None:
        """Test finding column with camel/snake conversion."""
        data_row = {"user_id": 123, "name": "Alice"}
        result = _find_matching_column("userId", data_row)
        self.assertEqual(result, 123)

    def test_find_matching_column_snake_camel(self) -> None:
        """Test finding column with snake/camel conversion."""
        data_row = {"userId": 123, "name": "Alice"}
        result = _find_matching_column("user_id", data_row)
        self.assertEqual(result, 123)

    def test_find_matching_column_suffix_match(self) -> None:
        """Test finding column with suffix match."""
        data_row = {"user_status": "active", "name": "Alice"}
        result = _find_matching_column("status", data_row)
        self.assertEqual(result, "active")

    def test_find_matching_column_not_found(self) -> None:
        """Test when column is not found returns None."""
        data_row = {"userId": 123, "name": "Alice"}
        result = _find_matching_column("nonexistent", data_row)
        self.assertIsNone(result)

    def test_generate_fallback_value_integer(self) -> None:
        """Test generating fallback for integer column."""
        column_types = {"user_id": "integer"}
        result = _generate_fallback_value("user_id", column_types)
        self.assertEqual(result, 0)

    def test_generate_fallback_value_string(self) -> None:
        """Test generating fallback for string column."""
        column_types = {"name": "varchar"}
        result = _generate_fallback_value("name", column_types)
        self.assertEqual(result, "generated_name")

    def test_generate_fallback_value_boolean(self) -> None:
        """Test generating fallback for boolean column."""
        column_types = {"active": "boolean"}
        result = _generate_fallback_value("active", column_types)
        self.assertEqual(result, False)

    def test_generate_fallback_value_unknown_type(self) -> None:
        """Test generating fallback for unknown column type."""
        column_types = {}
        result = _generate_fallback_value("unknown", column_types)
        self.assertEqual(result, "fallback_unknown")

    def test_bind_parameters_basic(self) -> None:
        """Test basic parameter binding."""
        params = [{"name": "userId", "type": "bind"}, {"name": "name", "type": "bind"}]
        data_rows = [{"userId": 1, "name": "Alice"}]
        column_types = {"userId": "integer", "name": "varchar"}

        result = bind_parameters(params, data_rows, column_types)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["userId"], 1)
        self.assertEqual(result[0]["name"], "Alice")

    def test_bind_parameters_with_fallback(self) -> None:
        """Test parameter binding with fallback values."""
        params = [
            {"name": "userId", "type": "bind"},
            {"name": "missing", "type": "bind"},
        ]
        data_rows = [{"userId": 1}]
        column_types = {"userId": "integer"}

        result = bind_parameters(params, data_rows, column_types)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["userId"], 1)
        self.assertIn("missing", result[0])

    def test_bind_parameters_empty_params(self) -> None:
        """Test binding with empty params returns empty list."""
        result = bind_parameters([], [{"userId": 1}], {})
        self.assertEqual(result, [])

    def test_bind_parameters_empty_data(self) -> None:
        """Test binding with empty data returns empty list."""
        params = [{"name": "userId", "type": "bind"}]
        result = bind_parameters(params, [], {})
        self.assertEqual(result, [])


class TestDataGenerator(unittest.TestCase):
    """Tests for data_generator module."""

    def test_generate_test_value_integer(self) -> None:
        """Test generating integer test values."""
        result = generate_test_value("integer")
        self.assertIsInstance(result, int)

    def test_generate_test_value_varchar(self) -> None:
        """Test generating varchar test values."""
        result = generate_test_value("varchar")
        self.assertEqual(result, "test_value")

    def test_generate_test_value_boolean(self) -> None:
        """Test generating boolean test values."""
        result = generate_test_value("boolean")
        self.assertEqual(result, True)

    def test_generate_test_value_numeric(self) -> None:
        """Test generating numeric test values."""
        result = generate_test_value("numeric")
        self.assertEqual(result, 0.0)

    def test_generate_test_value_timestamp(self) -> None:
        """Test generating timestamp test values."""
        result = generate_test_value("timestamp")
        from datetime import datetime

        self.assertIsInstance(result, datetime)

    def test_generate_test_value_unknown(self) -> None:
        """Test generating test value for unknown type."""
        result = generate_test_value("unknown_type")
        self.assertEqual(result, "placeholder")

    def test_generate_test_value_empty_string(self) -> None:
        """Test generating test value for empty string."""
        result = generate_test_value("")
        self.assertEqual(result, "placeholder")

    def test_generate_row(self) -> None:
        """Test generating a complete row."""
        column_types = {"id": "integer", "name": "varchar", "active": "boolean"}
        result = generate_row(column_types)

        self.assertIn("id", result)
        self.assertIn("name", result)
        self.assertIn("active", result)
        self.assertIsInstance(result["id"], int)
        self.assertEqual(result["name"], "test_value")
        self.assertEqual(result["active"], True)

    def test_generate_row_partial_match(self) -> None:
        """Test generating row with partial type matches."""
        column_types = {"id": "bigint", "description": "text"}
        result = generate_row(column_types)

        self.assertIn("id", result)
        self.assertIn("description", result)


if __name__ == "__main__":
    unittest.main()
