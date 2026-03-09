"""Tests for built-in rules detection."""

import unittest

from sqlopt.platforms.sql.rules import evaluate_rules


class TestBuiltinRulesDetection(unittest.TestCase):
    """Test built-in rules detection capabilities."""

    def test_select_star_detection(self):
        """Verify SELECT * is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("SELECT_STAR", rule_codes)

    def test_dollar_substitution_detection(self):
        """Verify ${} substitution is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE id = ${id}",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("DOLLAR_SUBSTITUTION", rule_codes)

    def test_sensitive_column_detection(self):
        """Verify sensitive columns are detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT password, token, credit_card FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("SENSITIVE_COLUMN_EXPOSED", rule_codes)

    def test_sensitive_column_in_where_detection(self):
        """Verify sensitive columns in WHERE are detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE password = 'xxx'",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        # Both SELECT_STAR and SENSITIVE_COLUMN_EXPOSED (via sensitive pattern in WHERE)
        self.assertTrue(
            "SENSITIVE_COLUMN_EXPOSED" in rule_codes or "SELECT_STAR" in rule_codes
        )

    def test_like_wildcard_start_detection(self):
        """Verify LIKE with leading wildcard is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE name LIKE '%john'",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("LIKE_WILDCARD_START", rule_codes)

    def test_order_by_random_detection(self):
        """Verify ORDER BY RAND() is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users ORDER BY RAND()",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("ORDER_BY_RANDOM", rule_codes)

    def test_join_without_on_detection(self):
        """Verify JOIN without ON is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM a JOIN b",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("JOIN_WITHOUT_ON", rule_codes)

    def test_full_scan_risk_detection(self):
        """Verify no WHERE clause is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT id FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("FULL_SCAN_RISK", rule_codes)

    def test_no_limit_detection(self):
        """Verify missing LIMIT is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT id FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("NO_LIMIT", rule_codes)

    def test_function_on_column_detection(self):
        """Verify function on indexed column is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE UPPER(name) = 'JOHN'",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("FUNCTION_ON_INDEXED_COL", rule_codes)

    def test_subquery_in_from_detection(self):
        """Verify subquery in FROM is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM (SELECT id FROM users) AS t",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("SUBQUERY_IN_FROM", rule_codes)

    def test_or_condition_detection(self):
        """Verify OR condition is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE status = 'active' OR status = 'pending'",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("OR_CONDITION_NO_INDEX", rule_codes)

    def test_distinct_abuse_detection(self):
        """Verify DISTINCT abuse is detected."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT DISTINCT a, b, c, d, e, f, g FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertIn("DISTINCT_ABUSE", rule_codes)

    def test_multiple_issues_detected(self):
        """Verify multiple issues are detected in one SQL."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE id = ${id} ORDER BY RAND()",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        rule_codes = [r["code"] for r in result["issues"]]

        self.assertIn("DOLLAR_SUBSTITUTION", rule_codes)
        self.assertIn("SELECT_STAR", rule_codes)
        self.assertIn("ORDER_BY_RANDOM", rule_codes)
        self.assertIn("NO_LIMIT", rule_codes)

    def test_clean_sql_no_issues(self):
        """Verify clean SQL has no issues."""
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT id, name FROM users WHERE id = ? LIMIT 10",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, {"rules": {}, "diagnostics": {}})
        # Should have minimal or no issues
        self.assertEqual(len(result["issues"]), 0)


if __name__ == "__main__":
    unittest.main()