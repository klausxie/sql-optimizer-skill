from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.platforms.sql.candidate_generation_support import dynamic_filter_from_alias_cleanup_sql
from sqlopt.platforms.sql.optimizer_sql import build_optimize_prompt, build_optimize_replay_request, generate_proposal


class OptimizeProposalTest(unittest.TestCase):
    def test_build_prompt_includes_template_context_for_dynamic_sql(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.findByList",
            "sql": "SELECT id FROM users WHERE id IN (#{item.id}, #{item.id})",
            "templateSql": 'SELECT id FROM users WHERE id IN <foreach collection="list" item="item">#{item.id}</foreach>',
            "dynamicFeatures": ["FOREACH", "INCLUDE"],
            "includeTrace": ["demo.user.BaseWhere"],
            "dynamicTrace": {"statementFeatures": ["FOREACH", "INCLUDE"], "includeFragments": [{"ref": "demo.user.BaseWhere", "dynamicFeatures": ["IF"]}]},
            "dynamicRenderIdentity": {
                "surfaceType": "COLLECTION_PREDICATE_BODY",
                "renderMode": "COLLECTION_PREDICATE_RENDERED",
                "foreachOrdinal": 0,
            },
            "riskFlags": [],
        }
        prompt = build_optimize_prompt(sql_unit, {"dbEvidenceSummary": {}, "issues": []})

        self.assertEqual(prompt["requiredContext"]["templateSql"], sql_unit["templateSql"])
        self.assertEqual(prompt["requiredContext"]["dynamicFeatures"], ["FOREACH", "INCLUDE"])
        self.assertEqual(prompt["optionalContext"]["includeTrace"], ["demo.user.BaseWhere"])
        self.assertEqual(prompt["optionalContext"]["dynamicTrace"]["includeFragments"][0]["ref"], "demo.user.BaseWhere")
        self.assertEqual(prompt["optionalContext"]["dynamicRenderIdentity"]["surfaceType"], "COLLECTION_PREDICATE_BODY")
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

    def test_build_optimize_replay_request_carries_dynamic_surface_contract(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword",
            "sql": "SELECT id, name FROM users WHERE (name ILIKE #{keyword} OR status = #{status})",
            "templateSql": (
                "SELECT id, name FROM users <where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keyword}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where>"
            ),
            "dynamicFeatures": ["WHERE", "CHOOSE"],
            "dynamicRenderIdentity": {
                "surfaceType": "CHOOSE_BRANCH_BODY",
                "renderMode": "CHOOSE_BRANCH_RENDERED",
                "branchOrdinal": 0,
            },
            "dynamicTrace": {
                "chooseBranchSurfaces": [
                    {"surfaceType": "CHOOSE_BRANCH_BODY", "branchOrdinal": 0, "renderedBranchSql": "name ILIKE #{keyword}"},
                ]
            },
        }

        request = build_optimize_replay_request(
            sql_unit,
            {"dbEvidenceSummary": {}, "planSummary": {}},
            {"provider": "opencode_run", "prompt_version": "v1"},
        )

        self.assertEqual(request["dynamicRenderIdentity"]["surfaceType"], "CHOOSE_BRANCH_BODY")
        self.assertEqual(
            request["dynamicTrace"]["chooseBranchSurfaces"][0]["renderedBranchSql"],
            "name ILIKE #{keyword}",
        )
        self.assertEqual(request["dynamicSurfaceContract"]["targetSurface"], "CHOOSE_BRANCH_BODY")
        self.assertTrue(request["dynamicSurfaceContract"]["branchLocalOnly"])
        self.assertTrue(request["dynamicSurfaceContract"]["forbidSetOperations"])
        self.assertTrue(request["dynamicSurfaceContract"]["forbidBranchMerge"])
        self.assertTrue(request["dynamicSurfaceContract"]["forbidWholeStatementRewrite"])

    def test_build_prompt_adds_choose_local_rewrite_constraints(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword",
            "sql": "SELECT id, name FROM users WHERE (name ILIKE #{keyword} OR status = #{status})",
            "templateSql": (
                "SELECT id, name FROM users <where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keyword}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where>"
            ),
            "dynamicFeatures": ["WHERE", "CHOOSE"],
            "dynamicRenderIdentity": {
                "surfaceType": "CHOOSE_BRANCH_BODY",
                "renderMode": "CHOOSE_BRANCH_RENDERED",
                "branchOrdinal": 0,
                "renderedBranchSql": "name ILIKE #{keyword}",
            },
            "dynamicTrace": {
                "chooseBranchSurfaces": [
                    {"surfaceType": "CHOOSE_BRANCH_BODY", "branchOrdinal": 0, "renderedBranchSql": "name ILIKE #{keyword}"},
                ]
            },
        }

        prompt = build_optimize_prompt(sql_unit, {"dbEvidenceSummary": {}, "issues": []})

        contract = prompt["rewriteConstraints"]["dynamicSurfaceContract"]
        self.assertEqual(contract["targetSurface"], "CHOOSE_BRANCH_BODY")
        self.assertEqual(contract["preferredOutcome"], "BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE")
        self.assertEqual(contract["allowedTemplateRewriteOps"], ["replace_choose_branch_body"])
        self.assertTrue(contract["branchLocalOnly"])
        self.assertTrue(contract["forbidSetOperations"])
        self.assertTrue(contract["forbidBranchMerge"])
        self.assertTrue(contract["forbidWholeStatementRewrite"])


if __name__ == "__main__":
    unittest.main()
