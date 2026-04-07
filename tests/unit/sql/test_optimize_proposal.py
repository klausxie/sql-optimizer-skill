from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.platforms.sql.candidate_generation_support import dynamic_filter_from_alias_cleanup_sql
from sqlopt.platforms.sql.optimizer_sql import build_optimize_prompt, generate_proposal


class OptimizeProposalTest(unittest.TestCase):
    def test_build_prompt_includes_template_context_for_dynamic_sql(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findByList",
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

    def test_dollar_substitution_blocks_actionability(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findUsers",
            "sql": "SELECT * FROM users WHERE status = #{status} ORDER BY ${orderBy}",
            "statementType": "SELECT",
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        self.assertEqual(proposal["actionability"]["tier"], "BLOCKED")
        self.assertEqual(proposal["actionability"]["score"], 0)
        self.assertIn("DOLLAR_SUBSTITUTION", proposal["actionability"]["blockedBy"])

    def test_static_sql_scores_as_high_value(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers",
            "sql": "SELECT id FROM users",
            "statementType": "SELECT",
            "dynamicFeatures": [],
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        self.assertEqual(proposal["actionability"]["tier"], "HIGH")
        self.assertEqual(proposal["actionability"]["autoPatchLikelihood"], "HIGH")

    def test_dynamic_include_reduces_patch_likelihood(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.dynamicUsers",
            "sql": "SELECT id FROM users WHERE id IN (#{id})",
            "statementType": "SELECT",
            "dynamicFeatures": ["IF", "INCLUDE"],
        }
        with patch("sqlopt.platforms.sql.optimizer_sql.collect_sql_evidence", return_value=({}, {})):
            proposal = generate_proposal(sql_unit, config={})

        self.assertEqual(proposal["actionability"]["autoPatchLikelihood"], "LOW")

    def test_dynamic_filter_from_alias_cleanup_restores_predicate_qualified_single_table_sql(self) -> None:
        original_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
        )

        self.assertEqual(
            dynamic_filter_from_alias_cleanup_sql(original_sql),
            (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
        )


if __name__ == "__main__":
    unittest.main()
