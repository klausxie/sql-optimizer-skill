"""Tests for param_example module."""
import pytest
from unittest.mock import patch, MagicMock

from sqlopt.application.v9_stages.param_example import (
    _camel_to_snake,
    _snake_to_camel,
    _remove_underscores,
    _extract_param_names,
    _find_matching_column,
    _get_example_value,
    generate_param_examples,
)


class TestCamelToSnake:
    """Tests for _camel_to_snake function."""

    def test_converts_simple_camel(self):
        """Test converts simple camelCase to snake_case."""
        assert _camel_to_snake("userName") == "user_name"

    def test_converts_multipart_camel(self):
        """Test converts multipart camelCase."""
        assert _camel_to_snake("myUserName") == "my_user_name"
        assert _camel_to_snake("someVeryLongName") == "some_very_long_name"

    def test_handles_all_caps(self):
        """Test handles all uppercase strings."""
        assert _camel_to_snake("USER") == "user"

    def test_handles_empty_string(self):
        """Test handles empty string."""
        assert _camel_to_snake("") == ""

    def test_handles_single_char(self):
        """Test handles single character."""
        assert _camel_to_snake("a") == "a"


class TestSnakeToCamel:
    """Tests for _snake_to_camel function."""

    def test_converts_simple_snake(self):
        """Test converts simple snake_case to camelCase."""
        assert _snake_to_camel("user_name") == "userName"

    def test_converts_multipart_snake(self):
        """Test converts multipart snake_case."""
        assert _snake_to_camel("my_user_name") == "myUserName"
        assert _snake_to_camel("some_very_long_name") == "someVeryLongName"

    def test_handles_empty_string(self):
        """Test handles empty string."""
        assert _snake_to_camel("") == ""

    def test_handles_single_word(self):
        """Test handles single word without underscores."""
        assert _snake_to_camel("user") == "user"


class TestRemoveUnderscores:
    """Tests for _remove_underscores function."""

    def test_removes_single_underscore(self):
        """Test removes single underscore."""
        assert _remove_underscores("user_name") == "username"

    def test_removes_multiple_underscores(self):
        """Test removes multiple underscores."""
        assert _remove_underscores("my_user_name") == "myusername"

    def test_handles_no_underscores(self):
        """Test handles string without underscores."""
        assert _remove_underscores("username") == "username"


class TestExtractParamNames:
    """Tests for _extract_param_names function."""

    def test_extracts_single_param(self):
        """Test extracts single parameter."""
        sql = "SELECT * FROM users WHERE id = #{userId}"
        assert _extract_param_names(sql) == ["userId"]

    def test_extracts_multiple_params(self):
        """Test extracts multiple parameters."""
        sql = "SELECT * FROM users WHERE id = #{userId} AND name = #{userName}"
        assert _extract_param_names(sql) == ["userId", "userName"]

    def test_extracts_no_params(self):
        """Test returns empty list when no params."""
        sql = "SELECT * FROM users"
        assert _extract_param_names(sql) == []

    def test_handles_weird_param_format(self):
        """Test handles unusual but valid param syntax."""
        sql = "SELECT * FROM #{tableName}"
        assert _extract_param_names(sql) == ["tableName"]


class TestFindMatchingColumn:
    """Tests for _find_matching_column function."""

    def test_exact_match_priority(self):
        """Test exact match is prioritized."""
        columns = [{"column": "userName"}, {"column": "user_name"}]
        result = _find_matching_column("userName", columns)
        assert result["column"] == "userName"

    def test_camel_to_snake_priority(self):
        """Test camel to snake conversion is second priority."""
        columns = [{"column": "user_name"}]
        result = _find_matching_column("userName", columns)
        assert result["column"] == "user_name"

    def test_snake_to_camel_priority(self):
        """Test snake to camel conversion is third priority."""
        columns = [{"column": "userName"}]
        result = _find_matching_column("user_name", columns)
        assert result["column"] == "userName"

    def test_underscore_removal_priority(self):
        """Test underscore removal is fourth priority."""
        columns = [{"column": "username"}]
        result = _find_matching_column("user_name", columns)
        assert result["column"] == "username"

    def test_returns_none_when_no_match(self):
        """Test returns None when no matching column found."""
        columns = [{"column": "otherColumn"}]
        result = _find_matching_column("userName", columns)
        assert result is None

    def test_handles_empty_columns(self):
        """Test handles empty columns list."""
        result = _find_matching_column("userName", [])
        assert result is None


class TestGetExampleValue:
    """Tests for _get_example_value function."""

    def test_type_mapping_integer(self):
        """Test INTEGER type mapping."""
        assert _get_example_value("INTEGER", False) == 1
        assert _get_example_value("INT", False) == 1
        assert _get_example_value("INT4", False) == 1

    def test_type_mapping_bigint(self):
        """Test BIGINT type mapping."""
        assert _get_example_value("BIGINT", False) == 1
        assert _get_example_value("INT8", False) == 1

    def test_type_mapping_smallint(self):
        """Test SMALLINT type mapping."""
        assert _get_example_value("SMALLINT", False) == 1
        assert _get_example_value("INT2", False) == 1

    def test_type_mapping_varchar(self):
        """Test VARCHAR type mapping."""
        assert _get_example_value("VARCHAR", False) == "example"
        assert _get_example_value("TEXT", False) == "example"
        assert _get_example_value("CHAR", False) == "example"

    def test_type_mapping_boolean(self):
        """Test BOOLEAN type mapping."""
        assert _get_example_value("BOOLEAN", False) is True
        assert _get_example_value("BOOL", False) is True

    def test_type_mapping_date(self):
        """Test DATE type mapping."""
        assert _get_example_value("DATE", False) == "2024-01-01"

    def test_type_mapping_timestamp(self):
        """Test TIMESTAMP type mapping."""
        assert _get_example_value("TIMESTAMP", False) == "2024-01-01T00:00:00"
        assert _get_example_value("DATETIME", False) == "2024-01-01T00:00:00"

    def test_type_mapping_time(self):
        """Test TIME type mapping."""
        assert _get_example_value("TIME", False) == "12:00:00"

    def test_type_mapping_float(self):
        """Test FLOAT/REAL type mapping."""
        assert _get_example_value("FLOAT", False) == 1.0
        assert _get_example_value("REAL", False) == 1.0

    def test_type_mapping_double(self):
        """Test DOUBLE type mapping."""
        assert _get_example_value("DOUBLE", False) == 1.0

    def test_type_mapping_decimal(self):
        """Test DECIMAL/NUMERIC type mapping."""
        assert _get_example_value("DECIMAL", False) == 1.0
        assert _get_example_value("NUMERIC", False) == 1.0

    def test_type_mapping_bytea(self):
        """Test BYTEA type mapping."""
        assert _get_example_value("BYTEA", False) == "\\x00"

    def test_type_mapping_json(self):
        """Test JSON/JSONB type mapping."""
        assert _get_example_value("JSON", False) == {}
        assert _get_example_value("JSONB", False) == {}

    def test_type_mapping_array(self):
        """Test ARRAY type mapping."""
        assert _get_example_value("ARRAY", False) == []

    def test_nullable_returns_none(self):
        """Test nullable columns return None regardless of type."""
        assert _get_example_value("INTEGER", True) is None
        assert _get_example_value("VARCHAR", True) is None
        assert _get_example_value("BOOLEAN", True) is None

    def test_unknown_type_returns_none(self):
        """Test unknown types return None."""
        assert _get_example_value("UNKNOWN_TYPE", False) is None

    def test_none_type_returns_none(self):
        """Test None type returns None."""
        assert _get_example_value(None, False) is None


class TestGenerateParamExamples:
    """Tests for generate_param_examples function."""

    def test_generate_param_examples(self):
        """Test full paramExample generation."""
        sql_units = [
            {"sqlKey": "findUser", "sql": "SELECT * FROM users WHERE id = #{userId} AND name = #{userName}"},
        ]
        schema_metadata = {
            "columns": [
                {"column": "userId", "dataType": "INTEGER", "isNullable": False},
                {"column": "userName", "dataType": "VARCHAR", "isNullable": True},
            ]
        }

        result = generate_param_examples(sql_units, schema_metadata)

        assert len(result) == 1
        assert result[0]["sqlKey"] == "findUser"
        assert result[0]["paramExample"]["userId"] == 1
        assert result[0]["paramExample"]["userName"] is None  # nullable

    def test_handles_empty_schema_metadata(self):
        """Test handles empty schema_metadata gracefully."""
        # Empty dict should return paramExample: {}
        sql_units_no_params = [{"sqlKey": "test", "sql": "SELECT 1"}]
        result = generate_param_examples(sql_units_no_params, {})
        assert result[0]["paramExample"] == {}

        # None should return paramExample: {}
        result = generate_param_examples(sql_units_no_params, None)
        assert result[0]["paramExample"] == {}

    def test_handles_missing_columns_key(self):
        """Test handles schema_metadata without columns key."""
        sql_units = [{"sqlKey": "test", "sql": "SELECT * FROM users"}]
        result = generate_param_examples(sql_units, {"other": "data"})
        assert result[0]["paramExample"] == {}

    def test_returns_none_for_unmatched_params(self):
        """Test unmatched parameters get None value."""
        sql_units = [
            {"sqlKey": "test", "sql": "SELECT * FROM users WHERE id = #{unknownParam}"},
        ]
        schema_metadata = {
            "columns": [
                {"column": "userId", "dataType": "INTEGER", "isNullable": False},
            ]
        }

        result = generate_param_examples(sql_units, schema_metadata)

        assert result[0]["paramExample"]["unknownParam"] is None

    def test_preserves_other_unit_fields(self):
        """Test preserves other fields in sql_unit."""
        sql_units = [
            {"sqlKey": "test", "sql": "SELECT * FROM users", "otherField": "preserveThis"},
        ]
        schema_metadata = {"columns": []}

        result = generate_param_examples(sql_units, schema_metadata)

        assert result[0]["otherField"] == "preserveThis"
        assert result[0]["sqlKey"] == "test"
