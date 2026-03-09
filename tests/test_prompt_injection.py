"""Tests for prompt injection features."""

import unittest

from sqlopt.platforms.sql.optimizer_sql import (
    build_optimize_prompt,
    _get_matched_prompt_injections,
    _get_system_prompts,
)


class TestPromptInjection(unittest.TestCase):
    """Test prompt injection features."""

    def test_build_optimize_prompt_without_config(self):
        """Verify prompt builds without config."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {"issues": [], "dbEvidenceSummary": {}, "triggeredRules": []}

        prompt = build_optimize_prompt(sql_unit, proposal)

        self.assertEqual(prompt["task"], "sql_optimize_candidate_generation")
        self.assertNotIn("systemPrompts", prompt)
        self.assertNotIn("ruleInjectedPrompts", prompt)

    def test_system_prompts_injection(self):
        """Verify system prompts are injected."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {"issues": [], "dbEvidenceSummary": {}, "triggeredRules": []}
        config = {
            "prompt_injections": {
                "system": [
                    {"content": "You are a SQL expert."},
                    {"content": "Focus on security."},
                ]
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertIn("systemPrompts", prompt)
        self.assertEqual(len(prompt["systemPrompts"]), 2)
        self.assertEqual(prompt["systemPrompts"][0], "You are a SQL expert.")

    def test_system_prompts_empty_content_filtered(self):
        """Verify empty system prompts are filtered."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {"issues": [], "dbEvidenceSummary": {}, "triggeredRules": []}
        config = {
            "prompt_injections": {
                "system": [
                    {"content": ""},
                    {"content": "Valid prompt"},
                ]
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertIn("systemPrompts", prompt)
        self.assertEqual(len(prompt["systemPrompts"]), 1)
        self.assertEqual(prompt["systemPrompts"][0], "Valid prompt")

    def test_rule_matched_prompts_injection(self):
        """Verify rule-matched prompts are injected when rule matches."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {
            "issues": [{"code": "SELECT_STAR"}],
            "dbEvidenceSummary": {},
            "triggeredRules": [{"ruleId": "SELECT_STAR"}],
        }
        config = {
            "prompt_injections": {
                "by_rule": [
                    {
                        "rule_id": "SELECT_STAR",
                        "prompt": "Avoid SELECT *, specify columns.",
                    },
                    {
                        "rule_id": "DOLLAR_SUBSTITUTION",
                        "prompt": "Check for SQL injection.",
                    },
                ]
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertIn("ruleInjectedPrompts", prompt)
        self.assertEqual(len(prompt["ruleInjectedPrompts"]), 1)
        self.assertEqual(
            prompt["ruleInjectedPrompts"][0], "Avoid SELECT *, specify columns."
        )

    def test_prompt_not_injected_when_no_match(self):
        """Verify prompts are not injected when no rule matches."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT id FROM users", "templateSql": ""}
        proposal = {
            "issues": [],
            "dbEvidenceSummary": {},
            "triggeredRules": [],  # No rules triggered
        }
        config = {
            "prompt_injections": {
                "by_rule": [
                    {
                        "rule_id": "SELECT_STAR",
                        "prompt": "This should not be injected",
                    }
                ]
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertNotIn("ruleInjectedPrompts", prompt)

    def test_multiple_rules_matched(self):
        """Verify multiple rule-matched prompts are injected."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {
            "issues": [{"code": "SELECT_STAR"}, {"code": "NO_LIMIT"}],
            "dbEvidenceSummary": {},
            "triggeredRules": [{"ruleId": "SELECT_STAR"}, {"ruleId": "NO_LIMIT"}],
        }
        config = {
            "prompt_injections": {
                "by_rule": [
                    {"rule_id": "SELECT_STAR", "prompt": "Prompt for SELECT_STAR"},
                    {"rule_id": "NO_LIMIT", "prompt": "Prompt for NO_LIMIT"},
                ]
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertIn("ruleInjectedPrompts", prompt)
        self.assertEqual(len(prompt["ruleInjectedPrompts"]), 2)

    def test_system_and_rule_prompts_together(self):
        """Verify system and rule prompts work together."""
        sql_unit = {"sqlKey": "test", "sql": "SELECT * FROM users", "templateSql": ""}
        proposal = {
            "issues": [{"code": "SELECT_STAR"}],
            "dbEvidenceSummary": {},
            "triggeredRules": [{"ruleId": "SELECT_STAR"}],
        }
        config = {
            "prompt_injections": {
                "system": [{"content": "System prompt"}],
                "by_rule": [{"rule_id": "SELECT_STAR", "prompt": "Rule prompt"}],
            }
        }

        prompt = build_optimize_prompt(sql_unit, proposal, config)

        self.assertIn("systemPrompts", prompt)
        self.assertIn("ruleInjectedPrompts", prompt)
        self.assertEqual(prompt["systemPrompts"][0], "System prompt")
        self.assertEqual(prompt["ruleInjectedPrompts"][0], "Rule prompt")


class TestGetSystemPrompts(unittest.TestCase):
    """Test _get_system_prompts helper function."""

    def test_get_system_prompts_empty(self):
        """Verify empty config returns empty list."""
        result = _get_system_prompts({})
        self.assertEqual(result, [])

    def test_get_system_prompts_valid(self):
        """Verify valid prompts are returned."""
        config = {
            "prompt_injections": {
                "system": [{"content": "Prompt 1"}, {"content": "Prompt 2"}]
            }
        }
        result = _get_system_prompts(config)
        self.assertEqual(len(result), 2)

    def test_get_system_prompts_empty_filtered(self):
        """Verify empty content is filtered."""
        config = {
            "prompt_injections": {
                "system": [{"content": ""}, {"content": "Valid"}]
            }
        }
        result = _get_system_prompts(config)
        self.assertEqual(len(result), 1)


class TestGetMatchedPromptInjections(unittest.TestCase):
    """Test _get_matched_prompt_injections helper function."""

    def test_no_by_rule_config(self):
        """Verify empty by_rule returns empty list."""
        triggered_rules = [{"ruleId": "SELECT_STAR"}]
        config = {"prompt_injections": {}}
        result = _get_matched_prompt_injections(triggered_rules, config)
        self.assertEqual(result, [])

    def test_rule_not_matched(self):
        """Verify prompts not injected when rule not triggered."""
        triggered_rules = [{"ruleId": "OTHER_RULE"}]
        config = {
            "prompt_injections": {
                "by_rule": [{"rule_id": "SELECT_STAR", "prompt": "Should not inject"}]
            }
        }
        result = _get_matched_prompt_injections(triggered_rules, config)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()