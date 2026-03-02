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


if __name__ == "__main__":
    unittest.main()
