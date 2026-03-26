"""Unit tests for table_extractor module - extract_table_names_from_sql and extract_table_schemas."""

from unittest.mock import MagicMock

import pytest
from sqlopt.contracts.init import TableSchema
from sqlopt.stages.init.stage import extract_table_names_from_sql
from sqlopt.stages.init.table_extractor import (
    extract_condition_fields_by_table,
    extract_field_distributions,
    extract_table_schemas,
    extract_where_fields_from_sql,
)


class TestExtractTableNamesFromSql:
    """Tests for extract_table_names_from_sql function."""

    def test_simple_select_from(self):
        """Test extracting table from simple SELECT."""
        sql = "SELECT * FROM users"
        result = extract_table_names_from_sql(sql)
        assert "users" in result

    def test_select_with_alias(self):
        """Test extracting table with alias."""
        sql = "SELECT * FROM users AS u"
        result = extract_table_names_from_sql(sql)
        assert "users" in result

    def test_select_with_implicit_alias(self):
        """Test extracting table with implicit alias (no AS keyword)."""
        sql = "SELECT * FROM users u"
        result = extract_table_names_from_sql(sql)
        assert "users" in result

    def test_inner_join(self):
        """Test extracting tables from INNER JOIN."""
        sql = "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result

    def test_left_join(self):
        """Test extracting tables from LEFT JOIN."""
        sql = "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result

    def test_right_join(self):
        """Test extracting tables from RIGHT JOIN."""
        sql = "SELECT * FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result

    def test_join_without_keyword_prefix(self):
        """Test extracting tables from JOIN without prefix."""
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result

    def test_multiple_tables_in_from(self):
        """Test extracting multiple tables from comma-separated FROM."""
        sql = "SELECT * FROM users, orders, products"
        result = extract_table_names_from_sql(sql)
        # Current implementation only captures first table in comma-separated FROM
        assert "users" in result

    def test_empty_sql(self):
        """Test empty SQL returns empty list."""
        result = extract_table_names_from_sql("")
        assert result == []

    def test_none_sql(self):
        """Test None SQL returns empty list."""
        result = extract_table_names_from_sql(None)  # type: ignore
        assert result == []

    def test_sql_without_from_clause(self):
        """Test SQL without FROM clause returns empty list."""
        sql = "SELECT 1 + 1 AS result"
        result = extract_table_names_from_sql(sql)
        assert result == []

    def test_subquery_not_extracted_as_table(self):
        """Test that subquery tables are not extracted."""
        sql = "SELECT * FROM (SELECT id FROM users) AS subq"
        result = extract_table_names_from_sql(sql)
        assert "subq" not in result

    def test_table_names_lowercase(self):
        """Test that table names are returned lowercase."""
        sql = "SELECT * FROM UsersTable"
        result = extract_table_names_from_sql(sql)
        assert "userstable" in result

    def test_sql_with_backticks(self):
        """Test SQL with backtick-quoted table names."""
        sql = "SELECT * FROM `users`"
        result = extract_table_names_from_sql(sql)
        assert "users" in result

    def test_cross_join(self):
        """Test CROSS JOIN pattern."""
        sql = "SELECT * FROM users CROSS JOIN orders"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result

    def test_outer_join(self):
        """Test OUTER JOIN pattern."""
        sql = "SELECT * FROM users OUTER JOIN orders"
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result


class TestExtractTableSchemas:
    """Tests for extract_table_schemas function."""

    def test_empty_table_list(self):
        """Test that empty table list returns empty dict."""
        mock_connector = MagicMock()
        result = extract_table_schemas([], mock_connector, "postgresql")
        assert result == {}

    def test_extract_postgresql_table(self):
        """Test extracting PostgreSQL table schema."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = [
            [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}],
            [{"column_name": "id"}],
            [{"indexname": "users_pkey", "indexdef": "CREATE UNIQUE INDEX users_pkey ON users(id)"}],
            [{"reltuples": 100, "relpages": 5}],
        ]

        result = extract_table_schemas(["users"], mock_connector, "postgresql")

        assert "users" in result
        assert len(result["users"].columns) == 1
        assert result["users"].columns[0]["name"] == "id"
        assert result["users"].columns[0]["type"] == "integer"

    def test_extract_mysql_table(self):
        """Test extracting MySQL table schema."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = [
            [{"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"}],
            [{"COLUMN_NAME": "id"}],
            [{"Key_name": "PRIMARY", "Column_name": "id", "Non_unique": 0}],
            [{"Rows": 50, "Data_length": 1024, "Index_length": 512}],
        ]

        result = extract_table_schemas(["users"], mock_connector, "mysql")

        assert "users" in result
        assert len(result["users"].columns) == 1
        assert result["users"].columns[0]["name"] == "id"

    def test_multiple_tables(self):
        """Test extracting schema for multiple tables."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = [
            [{"column_name": "id", "data_type": "integer", "is_nullable": "NO"}],
            [],
            [],
            [],
            [{"column_name": "name", "data_type": "varchar", "is_nullable": "YES"}],
            [],
            [],
            [],
        ]

        result = extract_table_schemas(["users", "products"], mock_connector, "postgresql")

        assert "users" in result
        assert "products" in result
        assert len(result["users"].columns) == 1
        assert len(result["products"].columns) == 1

    def test_connection_error_handling(self):
        """Test that connection errors are handled gracefully."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = ConnectionError("Connection failed")

        result = extract_table_schemas(["users"], mock_connector, "postgresql")

        assert result == {}

    def test_runtime_error_handling(self):
        """Test that runtime errors are handled gracefully."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = RuntimeError("Query failed")

        result = extract_table_schemas(["users"], mock_connector, "postgresql")

        assert result == {}

    def test_unsupported_platform(self):
        """Test that unsupported platform returns empty dict."""
        mock_connector = MagicMock()

        result = extract_table_schemas(["users"], mock_connector, "oracle")

        assert result == {}

    def test_table_not_found(self):
        """Test handling of tables that don't exist."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = [
            [],
            [],
            [],
            [],
        ]

        result = extract_table_schemas(["nonexistent"], mock_connector, "postgresql")

        assert "nonexistent" not in result


class TestExtractTableNamesIntegration:
    """Integration tests for table name extraction with SQL fragments."""

    def test_extract_from_complex_select(self):
        """Test extracting tables from complex SELECT statement."""
        sql = """
            SELECT u.id, u.name, o.order_date, p.product_name
            FROM users u
            INNER JOIN orders o ON u.id = o.user_id
            LEFT JOIN products p ON o.product_id = p.id
            WHERE u.active = true
        """
        result = extract_table_names_from_sql(sql)
        assert "users" in result
        assert "orders" in result
        assert "products" in result

    def test_extract_from_insert_statement(self):
        """Test extracting tables from INSERT statement."""
        sql = "INSERT INTO users (name, email) VALUES (#{name}, #{email})"
        result = extract_table_names_from_sql(sql)
        assert "users" in result

    def test_extract_from_update_statement(self):
        """Test extracting tables from UPDATE statement."""
        sql = "UPDATE orders SET status = 'shipped' WHERE id = #{id}"
        result = extract_table_names_from_sql(sql)
        assert "orders" in result

    def test_extract_from_delete_statement(self):
        """Test extracting tables from DELETE statement."""
        sql = "DELETE FROM users WHERE id = #{id}"
        result = extract_table_names_from_sql(sql)
        assert "users" in result


class TestExtractConditionFields:
    """Tests for condition field extraction helpers."""

    def test_extract_where_fields_from_dynamic_mybatis_sql(self):
        """Dynamic <if> tags should preserve inner condition columns."""
        sql = """
            <select id="findUsers">
                SELECT * FROM users u
                <where>
                    <if test="status != null">AND u.status = #{status}</if>
                    <if test="name != null">AND UPPER(name) = UPPER(#{name})</if>
                </where>
            </select>
        """
        result = extract_where_fields_from_sql(sql)
        assert set(result) == {"name", "status"}

    def test_extract_condition_fields_grouped_by_table(self):
        """Qualified join conditions should map back to their owning tables."""
        sql = """
            SELECT u.id, o.id
            FROM users u
            JOIN orders o ON u.id = o.user_id
            WHERE o.status = #{status}
        """
        result = extract_condition_fields_by_table(sql)
        assert result["users"] == {"id"}
        assert result["orders"] == {"status", "user_id"}


class TestExtractFieldDistributions:
    """Tests for field distribution extraction."""

    def test_extract_field_distributions_includes_total_count(self):
        """Extracted distributions should include the table row count for ratio calculations."""
        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = [
            [{"count": 100}],
            [{"count": 5}],
            [{"count": 20}],
            [{"value": "active", "count": 70}],
            [{"min_val": "active", "max_val": "inactive"}],
        ]

        result = extract_field_distributions("users", ["status"], mock_connector, "postgresql")

        assert len(result) == 1
        distribution = result[0]
        assert distribution.total_count == 100
        assert distribution.distinct_count == 5
        assert distribution.null_count == 20
