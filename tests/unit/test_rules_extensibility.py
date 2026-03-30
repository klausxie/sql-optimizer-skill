"""Tests for rules extensibility features."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.platforms.sql.rules import (
    _RULES,
    evaluate_rules,
    get_custom_rules_from_config,
    get_builtin_rules_enabled,
    load_external_rules_from_file,
)


class TestRulesExtensibility(unittest.TestCase):
    """Test rules extensibility features."""

    def test_builtin_rules_all_loaded(self):
        """Verify all 12 built-in rules are loaded."""
        self.assertEqual(len(_RULES), 12)
        expected_rules = [
            "DOLLAR_SUBSTITUTION",
            "SENSITIVE_COLUMN_EXPOSED",
            "SELECT_STAR",
            "FULL_SCAN_RISK",
            "SUBQUERY_IN_FROM",
            "OR_CONDITION_NO_INDEX",
            "FUNCTION_ON_INDEXED_COL",
            "LIKE_WILDCARD_START",
            "NO_LIMIT",
            "JOIN_WITHOUT_ON",
            "DISTINCT_ABUSE",
            "ORDER_BY_RANDOM",
        ]
        for rule_id in expected_rules:
            self.assertIn(rule_id, _RULES, f"Missing rule: {rule_id}")

    def test_builtin_rules_have_required_fields(self):
        """Verify all built-in rules have required fields."""
        for rule_id, rule in _RULES.items():
            self.assertIn("message", rule, f"{rule_id} missing message")
            self.assertIn("default_severity", rule, f"{rule_id} missing severity")
            self.assertIn("category", rule, f"{rule_id} missing category")

    def test_custom_inline_rules(self):
        """Verify custom inline rules are evaluated."""
        config = {
            "rules": {
                "custom_rules": [
                    {
                        "id": "MY_CUSTOM_RULE",
                        "message": "Custom rule message",
                        "default_severity": "warn",
                        "match": {"sql_contains": "CUSTOM_PATTERN"},
                        "action": {"suggestion_sql_template": "Fix it"},
                    }
                ]
            },
            "diagnostics": {},
        }
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users WHERE status = 'CUSTOM_PATTERN'",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, config)

        # Check custom rule was triggered
        rule_ids = [r["code"] for r in result["issues"]]
        self.assertIn("MY_CUSTOM_RULE", rule_ids)

    def test_builtin_rules_enable_disable(self):
        """Verify built-in rules can be enabled/disabled."""
        # Test disabling SELECT_STAR
        config = {
            "rules": {
                "builtin_rules": {
                    "SELECT_STAR": False,  # Disabled
                    "DOLLAR_SUBSTITUTION": True,
                }
            },
            "diagnostics": {},
        }
        enabled = get_builtin_rules_enabled(config)
        self.assertFalse(enabled.get("SELECT_STAR"))
        self.assertTrue(enabled.get("DOLLAR_SUBSTITUTION"))

    def test_builtin_rules_default_all_enabled(self):
        """Verify all rules are enabled by default."""
        config = {"rules": {}, "diagnostics": {}}
        enabled = get_builtin_rules_enabled(config)
        for rule_id in _RULES.keys():
            self.assertTrue(enabled.get(rule_id), f"{rule_id} should be enabled by default")

    def test_disabled_rule_not_triggered(self):
        """Verify disabled rules are not triggered."""
        config = {
            "rules": {
                "builtin_rules": {
                    "SELECT_STAR": False,
                }
            },
            "diagnostics": {},
            "rulepacks": [{"builtin": "performance"}],
        }
        sql_unit = {
            "sqlKey": "test",
            "sql": "SELECT * FROM users",
            "statementType": "SELECT",
        }
        result = evaluate_rules(sql_unit, config)

        # SELECT_STAR should not be triggered
        rule_codes = [r["code"] for r in result["issues"]]
        self.assertNotIn("SELECT_STAR", rule_codes)


class TestExternalRulesFile(unittest.TestCase):
    """Test external rules file loading."""

    def test_load_external_rules_from_nonexistent_file(self):
        """Verify non-existent file returns empty list."""
        config = {"rules": {"custom_rules_path": "/nonexistent/rules.yml"}}
        result = load_external_rules_from_file(Path("/tmp"), config)
        self.assertEqual(result, [])

    def test_load_external_rules_from_valid_file(self):
        """Verify valid YAML file is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_file = Path(tmpdir) / "rules.yml"
            rules_file.write_text(
                """
version: 1
rules:
  - id: EXTERNAL_RULE
    message: "External rule"
    match:
      sql_contains: "EXTERNAL"
"""
            )
            config = {"rules": {"custom_rules_path": str(rules_file)}}
            result = load_external_rules_from_file(Path(tmpdir), config)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "EXTERNAL_RULE")


class TestCustomRulesFromConfig(unittest.TestCase):
    """Test custom rules extraction from config."""

    def test_get_custom_rules_from_config_with_rules(self):
        """Verify custom rules are extracted."""
        config = {
            "rules": {
                "custom_rules": [
                    {"id": "RULE1"},
                    {"id": "RULE2"},
                ]
            }
        }
        result = get_custom_rules_from_config(config)
        self.assertEqual(len(result), 2)

    def test_get_custom_rules_from_config_empty(self):
        """Verify empty config returns empty list."""
        config = {"rules": {}}
        result = get_custom_rules_from_config(config)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()