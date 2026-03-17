"""Unit tests for Discovery module (Scanner and Parser classes)"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.discovery.scanner import Scanner, Parser


class ScannerTest(unittest.TestCase):
    """Tests for Scanner class"""

    def test_scan_single_mapper_file(self) -> None:
        """Scan a single XML mapper file"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            # Create a simple mapper file
            mapper_file = mapper_dir / "UserMapper.xml"
            mapper_file.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
</mapper>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            self.assertEqual(result.total_count, 1)
            self.assertEqual(len(result.sql_units), 1)
            self.assertEqual(result.sql_units[0]["statementId"], "findAll")
            self.assertEqual(result.sql_units[0]["statementType"], "select")

    def test_scan_multiple_mapper_files(self) -> None:
        """Scan multiple mapper files"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            # Create first mapper
            mapper1 = mapper_dir / "UserMapper.xml"
            mapper1.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
    <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
</mapper>""",
                encoding="utf-8",
            )

            # Create second mapper
            mapper2 = mapper_dir / "OrderMapper.xml"
            mapper2.write_text(
                """<mapper namespace="com.example.OrderMapper">
    <select id="findOrders">SELECT * FROM orders</select>
</mapper>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            self.assertEqual(result.total_count, 3)
            self.assertEqual(len(result.sql_units), 3)

            statement_ids = [unit["statementId"] for unit in result.sql_units]
            self.assertIn("findAll", statement_ids)
            self.assertIn("findById", statement_ids)
            self.assertIn("findOrders", statement_ids)

    def test_scan_with_namespace(self) -> None:
        """Handle namespace correctly"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            mapper_file = mapper_dir / "UserMapper.xml"
            mapper_file.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findById">SELECT * FROM users WHERE id = #{id}</select>
</mapper>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            self.assertEqual(len(result.sql_units), 1)
            unit = result.sql_units[0]

            # Verify namespace is correctly extracted
            self.assertEqual(unit["namespace"], "com.example.UserMapper")
            # Verify sqlKey includes namespace
            self.assertEqual(unit["sqlKey"], "com.example.UserMapper.findById")

    def test_scan_handles_parse_errors(self) -> None:
        """Graceful error handling for parse errors"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            # Create an invalid XML file (missing closing tag)
            invalid_mapper = mapper_dir / "InvalidMapper.xml"
            invalid_mapper.write_text(
                """<mapper namespace="com.example.InvalidMapper">
    <select id="findAll">SELECT * FROM users
</mapper>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            # Should have errors recorded
            self.assertGreater(len(result.errors), 0)
            # Should not have any SQL units from the invalid file
            self.assertEqual(result.total_count, 0)

    def test_scan_filters_non_mapper_xml(self) -> None:
        """Filter out non-mapper XML files"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            # Create a valid mapper file
            valid_mapper = mapper_dir / "UserMapper.xml"
            valid_mapper.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
</mapper>""",
                encoding="utf-8",
            )

            # Create a non-mapper XML file (no "mapper" in filename)
            non_mapper = mapper_dir / "config.xml"
            non_mapper.write_text(
                """<configuration>
    <settings>
        <setting name="cacheEnabled" value="true"/>
    </settings>
</configuration>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            # Only the mapper file should be scanned
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.sql_units[0]["statementId"], "findAll")

    def test_scan_respects_custom_globs(self) -> None:
        """Custom glob patterns are respected"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "mappers"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            # Create mapper in the custom location
            mapper_file = mapper_dir / "UserMapper.xml"
            mapper_file.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
</mapper>""",
                encoding="utf-8",
            )

            # Use custom glob pattern
            scanner = Scanner({"scan": {"mapper_globs": ["mappers/**/*.xml"]}})
            result = scanner.scan(root)

            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.sql_units[0]["statementId"], "findAll")

    def test_scan_returns_sql_units_with_required_fields(self) -> None:
        """Verify required fields in SQL units"""
        with tempfile.TemporaryDirectory(prefix="sqlopt_discovery_") as td:
            root = Path(td)
            mapper_dir = root / "src" / "main" / "resources"
            mapper_dir.mkdir(parents=True, exist_ok=True)

            mapper_file = mapper_dir / "UserMapper.xml"
            mapper_file.write_text(
                """<mapper namespace="com.example.UserMapper">
    <select id="findAll">SELECT * FROM users</select>
    <insert id="insertUser">INSERT INTO users (name) VALUES (#{name})</insert>
    <update id="updateUser">UPDATE users SET name = #{name}</update>
    <delete id="deleteUser">DELETE FROM users WHERE id = #{id}</delete>
</mapper>""",
                encoding="utf-8",
            )

            scanner = Scanner(
                {"scan": {"mapper_globs": ["src/main/resources/**/*.xml"]}}
            )
            result = scanner.scan(root)

            self.assertEqual(result.total_count, 4)

            for unit in result.sql_units:
                # Check required fields
                self.assertIn("sqlKey", unit)
                self.assertIn("xmlPath", unit)
                self.assertIn("namespace", unit)
                self.assertIn("statementId", unit)
                self.assertIn("sql", unit)
                self.assertIn("statementType", unit)

                # Verify statementType values
                self.assertIn(
                    unit["statementType"], ["select", "insert", "update", "delete"]
                )


class ParserTest(unittest.TestCase):
    """Tests for Parser class"""

    def test_parse_detects_select_statement(self) -> None:
        """Detect SELECT statements"""
        parser = Parser()

        result = parser.parse("SELECT * FROM users WHERE id = 1")

        self.assertEqual(result["type"], "SELECT")
        self.assertIn("SELECT", result["raw_sql"])

    def test_parse_detects_insert_statement(self) -> None:
        """Detect INSERT statements"""
        parser = Parser()

        result = parser.parse(
            "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
        )

        self.assertEqual(result["type"], "INSERT")
        self.assertIn("INSERT", result["raw_sql"])

    def test_parse_detects_update_statement(self) -> None:
        """Detect UPDATE statements"""
        parser = Parser()

        result = parser.parse("UPDATE users SET name = 'John' WHERE id = 1")

        self.assertEqual(result["type"], "UPDATE")
        self.assertIn("UPDATE", result["raw_sql"])

    def test_parse_detects_delete_statement(self) -> None:
        """Detect DELETE statements"""
        parser = Parser()

        result = parser.parse("DELETE FROM users WHERE id = 1")

        self.assertEqual(result["type"], "DELETE")
        self.assertIn("DELETE", result["raw_sql"])

    def test_parse_extracts_table_names(self) -> None:
        """Extract table names from SQL"""
        parser = Parser()

        # Test SELECT with FROM
        result = parser.parse("SELECT * FROM users")
        self.assertIn("users", result["tables"])

        # Test UPDATE
        result = parser.parse("UPDATE users SET name = 'John'")
        self.assertIn("users", result["tables"])

        # Test INSERT INTO
        result = parser.parse("INSERT INTO users (name) VALUES ('John')")
        self.assertIn("users", result["tables"])

        # Test DELETE FROM
        result = parser.parse("DELETE FROM users WHERE id = 1")
        self.assertIn("users", result["tables"])

        # Test multiple tables
        result = parser.parse("SELECT * FROM users u JOIN orders o ON u.id = o.user_id")
        self.assertIn("users", result["tables"])
        self.assertIn("orders", result["tables"])

    def test_parse_extracts_where_conditions(self) -> None:
        """Extract WHERE conditions from SQL"""
        parser = Parser()

        # Single condition
        result = parser.parse("SELECT * FROM users WHERE id = 1")
        self.assertGreater(len(result["conditions"]), 0)

        # Multiple conditions with AND
        result = parser.parse(
            "SELECT * FROM users WHERE name = 'John' AND status = 'active'"
        )
        self.assertGreaterEqual(len(result["conditions"]), 1)

        # Multiple conditions with OR
        result = parser.parse(
            "SELECT * FROM users WHERE name = 'John' OR name = 'Jane'"
        )
        self.assertGreaterEqual(len(result["conditions"]), 1)

        # No WHERE clause
        result = parser.parse("SELECT * FROM users")
        self.assertEqual(len(result["conditions"]), 0)

    def test_parse_extracts_joins(self) -> None:
        """Extract JOINs from SQL"""
        parser = Parser()

        # INNER JOIN
        result = parser.parse(
            "SELECT * FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        self.assertIn("orders", result["joins"])

        # LEFT JOIN
        result = parser.parse(
            "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
        self.assertIn("orders", result["joins"])

        # RIGHT JOIN
        result = parser.parse(
            "SELECT * FROM users RIGHT JOIN orders ON users.id = orders.user_id"
        )
        self.assertIn("orders", result["joins"])

        # Multiple JOINs
        result = parser.parse(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id JOIN products p ON o.product_id = p.id"
        )
        self.assertIn("orders", result["joins"])
        self.assertIn("products", result["joins"])

        # No JOIN
        result = parser.parse("SELECT * FROM users")
        self.assertEqual(len(result["joins"]), 0)


if __name__ == "__main__":
    unittest.main()
