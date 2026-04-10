from __future__ import annotations

import unittest
from pathlib import Path

from sqlopt.platforms.sql.patch_utils import derive_patch_target_family
from sqlopt.stages.patch_select import build_patch_selection_context


class PatchSelectionTest(unittest.TestCase):
    def test_choose_primary_sentinel_selects_local_safe_baseline_family(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE upper(name) ILIKE upper(#{keyword})",
            "xmlPath": str(Path(__file__).resolve()),
            "namespace": "demo.user.advanced",
            "statementId": "findUsersByKeyword",
            "templateSql": (
                "SELECT id, name, email, status, created_at, updated_at FROM users "
                "<where><choose><when test=\"keyword != null and keyword != ''\">"
                "upper(name) ILIKE upper(#{keyword})</when><otherwise>status = 'ACTIVE'</otherwise></choose></where>"
            ),
            "dynamicFeatures": ["WHERE", "CHOOSE"],
            "dynamicTrace": {"statementFeatures": ["WHERE", "CHOOSE"]},
        }
        acceptance = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword",
            "status": "PASS",
            "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE name ILIKE #{keyword}",
            "selectedCandidateId": "candidate_1",
            "selectedCandidateSource": "llm",
            "equivalence": {"checked": True, "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
            "semanticEquivalence": {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            },
        }

        selection = build_patch_selection_context(
            sql_unit=sql_unit,
            acceptance=acceptance,
            fragment_catalog={},
            config={},
        )

        self.assertEqual(selection.family, "DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP")
        self.assertEqual(selection.dynamic_template["patchSurface"], "CHOOSE_BRANCH_BODY")
        self.assertEqual(selection.dynamic_template["baselineFamily"], "DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP")
        self.assertEqual(
            selection.dynamic_template["surfaceContract"]["rewriteOpPreview"]["op"],
            "replace_choose_branch_body",
        )
        self.assertFalse(selection.dynamic_template["surfaceContract"]["surfaceFallbackAllowed"])
        self.assertEqual(selection.selected_patch_strategy["strategyType"], "EXACT_TEMPLATE_EDIT")
        self.assertEqual(selection.rewrite_materialization["mode"], "DYNAMIC_CHOOSE_BRANCH_TEMPLATE_SAFE")
        self.assertTrue(selection.rewrite_materialization["replayVerified"])
        self.assertEqual(selection.template_rewrite_ops[0]["op"], "replace_choose_branch_body")

    def test_collection_review_only_summary_carries_surface_contract_preview(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.findOrdersByUserIdsAndStatus",
            "sql": (
                "SELECT id, user_id, order_no, amount, status, created_at "
                "FROM orders WHERE user_id IN (#{userId}) AND status = #{status}"
            ),
            "xmlPath": str(Path(__file__).resolve()),
            "namespace": "demo.order.harness",
            "statementId": "findOrdersByUserIdsAndStatus",
            "templateSql": (
                'SELECT <include refid="OrderColumns" /> FROM orders <where>'
                '<foreach collection="userIds" item="userId" open="user_id IN (" separator="," close=")">'
                "#{userId}</foreach>"
                '<if test="status != null and status != \'\'">AND status = #{status}</if>'
                "</where>"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH", "IF"],
            "dynamicTrace": {
                "statementFeatures": ["INCLUDE", "WHERE", "FOREACH", "IF"],
                "includeFragments": [{"ref": "demo.order.harness.OrderColumns", "dynamicFeatures": []}],
            },
        }
        acceptance = {
            "sqlKey": "demo.order.harness.findOrdersByUserIdsAndStatus",
            "status": "PASS",
            "rewrittenSql": (
                "SELECT id, user_id, order_no, amount, status, created_at "
                "FROM orders WHERE user_id IN (#{userId}) AND status = #{status}"
            ),
            "selectedCandidateId": "candidate_1",
            "selectedCandidateSource": "llm",
            "equivalence": {"checked": True, "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
            "semanticEquivalence": {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            },
        }

        selection = build_patch_selection_context(
            sql_unit=sql_unit,
            acceptance=acceptance,
            fragment_catalog={},
            config={},
        )

        self.assertEqual(selection.dynamic_template["patchSurface"], "COLLECTION_PREDICATE_BODY")
        self.assertEqual(
            selection.dynamic_template["surfaceContract"]["rewriteOpPreview"]["op"],
            "replace_collection_predicate_body",
        )
        self.assertEqual(
            selection.dynamic_template["surfaceContract"]["patchFamilyPreview"],
            "DYNAMIC_COLLECTION_PREDICATE_LOCAL_CLEANUP",
        )
        self.assertEqual(selection.rewrite_materialization["mode"], "DYNAMIC_COLLECTION_PREDICATE_TEMPLATE_SAFE")
        self.assertFalse(selection.rewrite_materialization["replayVerified"])
        self.assertEqual(selection.template_rewrite_ops[0]["op"], "replace_collection_predicate_body")

    def test_static_qualified_alias_cleanup_keeps_exact_template_edit(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersProjectedQualifiedAliases",
            "sql": (
                "SELECT u.id AS id, u.name AS name, u.email AS email, u.status AS status, "
                "u.created_at AS created_at, u.updated_at AS updated_at "
                "FROM users u ORDER BY u.created_at DESC"
            ),
            "xmlPath": str(Path(__file__).resolve()),
            "namespace": "demo.user.advanced",
            "statementId": "listUsersProjectedQualifiedAliases",
            "templateSql": (
                "SELECT u.id AS id, u.name AS name, u.email AS email, u.status AS status, "
                "u.created_at AS created_at, u.updated_at AS updated_at "
                "FROM users u ORDER BY u.created_at DESC"
            ),
            "dynamicFeatures": [],
        }
        acceptance = {
            "sqlKey": "demo.user.advanced.listUsersProjectedQualifiedAliases",
            "status": "PASS",
            "rewrittenSql": "SELECT u.id, u.name, u.email, u.status, u.created_at, u.updated_at FROM users u ORDER BY u.created_at DESC",
            "selectedCandidateId": "candidate_1",
            "selectedCandidateSource": "llm",
            "equivalence": {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            },
            "semanticEquivalence": {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            },
        }

        selection = build_patch_selection_context(
            sql_unit=sql_unit,
            acceptance=acceptance,
            fragment_catalog={},
            config={},
        )

        self.assertEqual(selection.family, "STATIC_ALIAS_PROJECTION_CLEANUP")
        self.assertEqual(selection.patchability.get("blockingReasons"), [])
        self.assertEqual(selection.selected_patch_strategy["strategyType"], "EXACT_TEMPLATE_EDIT")
        self.assertEqual(selection.rewrite_materialization["mode"], "STATEMENT_SQL")

    def test_derive_patch_target_family_prefers_exists_strategy_over_dynamic_baseline(self) -> None:
        family = derive_patch_target_family(
            original_sql="SELECT id FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id)",
            rewritten_sql="SELECT id FROM users u",
            rewrite_facts={
                "dynamicTemplate": {
                    "capabilityProfile": {
                        "baselineFamily": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
                    }
                }
            },
            rewrite_materialization=None,
            selected_patch_strategy={"strategyType": "SAFE_EXISTS_REWRITE"},
        )

        self.assertEqual(family, "STATIC_EXISTS_REWRITE")

    def test_derive_patch_target_family_prefers_union_strategy_over_dynamic_baseline(self) -> None:
        family = derive_patch_target_family(
            original_sql="SELECT * FROM (SELECT id FROM shipments WHERE status = 'SHIPPED' UNION SELECT id FROM shipments WHERE status = 'DELIVERED') su",
            rewritten_sql="SELECT id FROM shipments WHERE status = 'SHIPPED' UNION SELECT id FROM shipments WHERE status = 'DELIVERED'",
            rewrite_facts={
                "dynamicTemplate": {
                    "capabilityProfile": {
                        "baselineFamily": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
                    }
                }
            },
            rewrite_materialization=None,
            selected_patch_strategy={"strategyType": "SAFE_UNION_COLLAPSE"},
        )

        self.assertEqual(family, "STATIC_UNION_COLLAPSE")

    def test_derive_patch_target_family_uses_one_to_one_registry_mapping_for_join_strategy(self) -> None:
        family = derive_patch_target_family(
            original_sql="SELECT * FROM orders o LEFT JOIN users u ON u.id = o.user_id",
            rewritten_sql="SELECT * FROM orders o INNER JOIN users u ON u.id = o.user_id",
            rewrite_facts={
                "dynamicTemplate": {
                    "capabilityProfile": {
                        "baselineFamily": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
                    }
                }
            },
            rewrite_materialization=None,
            selected_patch_strategy={"strategyType": "SAFE_JOIN_LEFT_TO_INNER"},
        )

        self.assertEqual(family, "STATIC_JOIN_LEFT_TO_INNER")

    def test_derive_patch_target_family_keeps_generic_wrapper_collapse_explicit(self) -> None:
        family = derive_patch_target_family(
            original_sql="SELECT id FROM (SELECT id FROM users) u",
            rewritten_sql="SELECT id FROM users",
            rewrite_facts={},
            rewrite_materialization=None,
            selected_patch_strategy={"strategyType": "SAFE_WRAPPER_COLLAPSE"},
        )

        self.assertEqual(family, "STATIC_WRAPPER_COLLAPSE")


if __name__ == "__main__":
    unittest.main()
