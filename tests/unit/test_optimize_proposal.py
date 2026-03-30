from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.platforms.sql.optimizer_sql import build_optimize_prompt, generate_proposal


class OptimizeProposalTest(unittest.TestCase):
    def test_build_prompt_includes_template_context_for_dynamic_sql(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findByList#v1",
            "sql": "SELECT id FROM users WHERE id IN (#{item.id}, #{item.id})",
            "templateSql": 'SELECT id FROM users WHERE id IN <foreach collection="list" item="item">#{item.id}</foreach>',
            "dynamicFeatures": ["FOREACH", "INCLUDE"],
            "includeTrace": ["demo.user.BaseWhere"],
            "dynamicTrace": {"statementFeatures": ["FOREACH", "INCLUDE"], "includeFragments": [{"ref": "demo.user.BaseWhere", "dynamicFeatures": ["IF"]}]},
            "riskFlags": [],
        }
        prompt = build_optimize_prompt(sql_unit, {"dbEvidenceSummary": {}, "issues": []})

        self.assertEqual(prompt["requiredContext"]["templateSql"], sql_unit["templateSql"])
        self.assertEqual(prompt["requiredContext"]["dynamicFeatures"], ["FOREACH", "INCLUDE"])
        self.assertEqual(prompt["optionalContext"]["includeTrace"], ["demo.user.BaseWhere"])
        self.assertEqual(prompt["optionalContext"]["dynamicTrace"]["includeFragments"][0]["ref"], "demo.user.BaseWhere")
        self.assertTrue(prompt["rewriteConstraints"]["dynamicTemplateRequiresTemplateAwarePatch"])

    def test_marks_dollar_substitution_as_issue(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findUsers#v1",
            "sql": "SELECT * FROM users WHERE status = #{status} ORDER BY ${orderBy}",
            "statementType": "SELECT",
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        codes = [x.get("code") for x in proposal.get("issues", [])]
        self.assertIn("DOLLAR_SUBSTITUTION", codes)
        self.assertEqual(proposal.get("verdict"), "CAN_IMPROVE")
        self.assertEqual(proposal["actionability"]["tier"], "BLOCKED")
        self.assertEqual(proposal["actionability"]["score"], 0)
        self.assertIn("DOLLAR_SUBSTITUTION", proposal["actionability"]["blockedBy"])
        self.assertEqual(proposal["triggeredRules"][0]["ruleId"], "DOLLAR_SUBSTITUTION")
        self.assertEqual(proposal.get("recommendedSuggestionIndex"), 0)

    def test_static_select_star_scores_as_high_value(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers#v1",
            "sql": "SELECT * FROM users",
            "statementType": "SELECT",
            "dynamicFeatures": [],
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        self.assertEqual(proposal["actionability"]["tier"], "HIGH")
        self.assertEqual(proposal["actionability"]["autoPatchLikelihood"], "HIGH")
        self.assertEqual(proposal.get("recommendedSuggestionIndex"), 0)

    def test_dynamic_include_reduces_patch_likelihood(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.dynamicUsers#v1",
            "sql": "SELECT id FROM users WHERE id IN (#{id})",
            "statementType": "SELECT",
            "dynamicFeatures": ["IF", "INCLUDE"],
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        self.assertEqual(proposal["actionability"]["autoPatchLikelihood"], "LOW")

    def test_diagnostics_can_disable_performance_rulepack(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers#v1",
            "sql": "SELECT * FROM users",
            "statementType": "SELECT",
            "dynamicFeatures": [],
        }
        config = {"diagnostics": {"rulepacks": [{"builtin": "core"}], "severity_overrides": {}, "disabled_rules": []}}
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config=config)

        codes = [x.get("code") for x in proposal.get("issues", [])]
        self.assertNotIn("SELECT_STAR", codes)
        self.assertEqual(proposal.get("recommendedSuggestionIndex"), None)

    def test_diagnostics_can_override_rule_severity(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers#v1",
            "sql": "SELECT * FROM users",
            "statementType": "SELECT",
            "dynamicFeatures": [],
        }
        config = {
            "diagnostics": {
                "rulepacks": [{"builtin": "core"}, {"builtin": "performance"}],
                "severity_overrides": {"SELECT_STAR": "error"},
                "disabled_rules": [],
            }
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config=config)

        select_star_issue = next(x for x in proposal["issues"] if x["code"] == "SELECT_STAR")
        self.assertEqual(select_star_issue["severity"], "error")

    def test_external_diagnostics_rule_can_block_actionability(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers#v1",
            "sql": "SELECT id FROM users",
            "statementType": "SELECT",
            "dynamicFeatures": [],
        }
        config = {
            "diagnostics": {
                "rulepacks": [{"file": "/tmp/project_rules.yml"}],
                "severity_overrides": {},
                "disabled_rules": [],
                "loaded_rulepacks": [
                    {
                        "file": "/tmp/project_rules.yml",
                        "rules": [
                            {
                                "rule_id": "REQUIRE_LIMIT",
                                "message": "list queries should be bounded",
                                "default_severity": "warn",
                                "match": {"statement_type_is": "SELECT", "sql_contains": "from users"},
                                "action": {
                                    "suggestion_sql_template": "SELECT id FROM users LIMIT 100",
                                    "block_actionability": True,
                                },
                            }
                        ],
                    }
                ],
            }
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config=config)

        self.assertEqual(proposal["issues"][0]["code"], "REQUIRE_LIMIT")
        self.assertEqual(proposal["issues"][0]["severity"], "warn")
        self.assertEqual(proposal["triggeredRules"][0]["builtin"], "file")
        self.assertEqual(proposal["triggeredRules"][0]["sourceRef"], "/tmp/project_rules.yml")
        self.assertTrue(proposal["triggeredRules"][0]["blocksActionability"])
        self.assertEqual(proposal["actionability"]["tier"], "BLOCKED")
        self.assertIn("REQUIRE_LIMIT", proposal["actionability"]["blockedBy"])
        self.assertEqual(proposal["recommendedSuggestionIndex"], 0)


if __name__ == "__main__":
    unittest.main()
