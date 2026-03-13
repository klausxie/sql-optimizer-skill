from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.rewrite_facts import build_rewrite_facts, build_rewrite_facts_model


class RewriteFactsTest(unittest.TestCase):
    def test_build_rewrite_facts_model_preserves_contract_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rewrite_facts_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="UserBaseColumns">id, name</sql>
  <sql id="userBaseQuery">SELECT <include refid="UserBaseColumns" /> FROM users</sql>
  <select id="countUser">select count(1) from (<include refid="userBaseQuery" />) tmp</select>
</mapper>""",
                encoding="utf-8",
            )
            columns_ref = f"{xml_path.resolve()}::demo.user.UserBaseColumns"
            base_ref = f"{xml_path.resolve()}::demo.user.userBaseQuery"
            sql_unit = {
                "sqlKey": "demo.user.countUser#v2",
                "sql": "select count(1) from ( SELECT id, name FROM users ) tmp",
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "countUser",
                "templateSql": 'select count(1) from (<include refid="userBaseQuery" />) tmp',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": base_ref, "properties": [], "bindingHash": "base"}],
                "primaryFragmentTarget": base_ref,
            }
            fragment_catalog = {
                base_ref: {
                    "fragmentKey": base_ref,
                    "xmlPath": str(xml_path),
                    "namespace": "demo.user",
                    "templateSql": 'SELECT <include refid="UserBaseColumns" /> FROM users',
                    "dynamicFeatures": ["INCLUDE"],
                    "includeBindings": [{"ref": columns_ref, "properties": [], "bindingHash": "cols"}],
                },
                columns_ref: {
                    "fragmentKey": columns_ref,
                    "xmlPath": str(xml_path),
                    "namespace": "demo.user",
                    "templateSql": "id, name",
                    "dynamicFeatures": [],
                    "includeBindings": [],
                },
            }
            equivalence = {
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
            }

            model = build_rewrite_facts_model(
                sql_unit,
                "SELECT COUNT(*) FROM users",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
            )
            payload = build_rewrite_facts(
                sql_unit,
                "SELECT COUNT(*) FROM users",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
            )

        self.assertTrue(model.effective_change)
        self.assertTrue(model.wrapper_query.collapsible)
        self.assertEqual(model.semantic.fingerprint_strength, "EXACT")
        self.assertEqual(payload, model.to_dict())

    def test_build_rewrite_facts_model_captures_simple_cte_inline_candidate(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listRecentUsersViaCte#v11",
            "sql": (
                "WITH recent_users AS ( SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE created_at >= #{createdAfter} ) "
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM recent_users ORDER BY created_at DESC LIMIT 20"
            ),
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listRecentUsersViaCte",
            "templateSql": (
                "WITH recent_users AS ( SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE created_at >= #{createdAfter} ) "
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM recent_users ORDER BY created_at DESC LIMIT 20"
            ),
            "dynamicFeatures": [],
        }
        equivalence = {
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
        }
        semantic_equivalence = {
            "status": "PASS",
            "confidence": "HIGH",
            "evidenceLevel": "DB_FINGERPRINT",
            "hardConflicts": [],
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
            {},
            equivalence,
            semantic_equivalence,
        )

        self.assertTrue(model.cte_query.present)
        self.assertTrue(model.cte_query.collapsible)
        self.assertTrue(model.cte_query.inline_candidate)
        self.assertEqual(model.cte_query.cte_name, "recent_users")
        self.assertEqual(
            model.cte_query.inlined_sql,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
        )

    def test_build_rewrite_facts_model_captures_static_include_dynamic_template_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersRecentPaged#v4",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listUsersRecentPaged",
            "templateSql": 'SELECT <include refid="AdvancedUserColumns" /> FROM users ORDER BY created_at DESC LIMIT 100',
            "dynamicFeatures": ["INCLUDE"],
            "dynamicTrace": {
                "statementFeatures": ["INCLUDE"],
                "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
            },
            "includeBindings": [{"ref": "demo.user.advanced.AdvancedUserColumns", "properties": [], "bindingHash": "base"}],
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 50",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.statement_features, ["INCLUDE"])
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "STATIC_INCLUDE_ONLY")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.dynamic_template.capability_profile.patch_surface, "STATEMENT_BODY")
        self.assertTrue(model.dynamic_template.capability_profile.template_preserving_candidate)

    def test_build_rewrite_facts_model_marks_static_include_with_properties_as_fragment_dependent(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersWithBoundInclude#v1",
            "sql": "SELECT id, name FROM users ORDER BY created_at DESC",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listUsersWithBoundInclude",
            "templateSql": 'SELECT <include refid="AdvancedUserColumns"><property name="alias" value="u"/></include> FROM users u ORDER BY created_at DESC',
            "dynamicFeatures": ["INCLUDE"],
            "dynamicTrace": {
                "statementFeatures": ["INCLUDE"],
                "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
            },
            "includeBindings": [
                {
                    "ref": "demo.user.advanced.AdvancedUserColumns",
                    "properties": [{"name": "alias", "value": "u"}],
                    "bindingHash": "bound",
                }
            ],
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name FROM users u ORDER BY created_at DESC",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "STATIC_INCLUDE_ONLY")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "REVIEW_REQUIRED")
        self.assertEqual(model.dynamic_template.capability_profile.blocker_family, "STATIC_INCLUDE_FRAGMENT_DEPENDENT")
        self.assertEqual(model.dynamic_template.capability_profile.blockers, ["STATIC_INCLUDE_FRAGMENT_DEPENDENT"])

    def test_build_rewrite_facts_model_captures_foreach_dynamic_template_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.findOrdersByNos#v1",
            "sql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "findOrdersByNos",
            "templateSql": (
                'SELECT <include refid="OrderColumns" /> FROM orders <where> '
                '<foreach collection="orderNos" item="orderNo" open="order_no IN (" separator="," close=")">'
                "#{orderNo}</foreach></where>"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
            "dynamicTrace": {
                "statementFeatures": ["INCLUDE", "WHERE", "FOREACH"],
                "includeFragments": [{"ref": "demo.order.harness.OrderColumns", "dynamicFeatures": []}],
            },
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "FOREACH_IN_PREDICATE")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "REVIEW_REQUIRED")
        self.assertEqual(model.dynamic_template.capability_profile.patch_surface, "WHERE_CLAUSE")
        self.assertEqual(model.dynamic_template.capability_profile.blocker_family, "FOREACH_INCLUDE_PREDICATE")

    def test_build_rewrite_facts_model_marks_complex_dynamic_filter_as_unsafe_statement_rewrite(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword#v8",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE name ILIKE #{keyword}",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "findUsersByKeyword",
            "templateSql": (
                "SELECT id, name, email, status, created_at, updated_at FROM users "
                "<where><choose><when test=\"keyword != null and keyword != ''\">"
                "name ILIKE #{keyword}</when><otherwise>status = 'ACTIVE'</otherwise></choose></where>"
            ),
            "dynamicFeatures": ["WHERE", "CHOOSE"],
            "dynamicTrace": {"statementFeatures": ["WHERE", "CHOOSE"]},
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE name ILIKE #{keyword}",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "REVIEW_REQUIRED")
        self.assertEqual(model.dynamic_template.capability_profile.blocker_family, "DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE")

    def test_build_rewrite_facts_model_marks_dynamic_filter_select_list_cleanup_as_safe_baseline(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersFilteredAliased#v17",
            "sql": (
                "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listUsersFilteredAliased",
            "templateSql": (
                "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                "FROM users <where><if test=\"status != null and status != ''\">AND status = #{status}</if>"
                "<if test=\"createdAfter != null\">AND created_at &gt;= #{createdAfter}</if></where> ORDER BY created_at DESC"
            ),
            "dynamicFeatures": ["WHERE", "IF"],
            "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.dynamic_template.capability_profile.patch_surface, "STATEMENT_BODY")
        self.assertEqual(model.dynamic_template.capability_profile.baseline_family, "DYNAMIC_FILTER_SELECT_LIST_CLEANUP")

    def test_build_rewrite_facts_model_marks_dynamic_filter_from_alias_cleanup_as_safe_baseline(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listUsersFilteredTableAliased#v18",
            "sql": (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users u WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listUsersFilteredTableAliased",
            "templateSql": (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users u <where><if test=\"status != null and status != ''\">AND status = #{status}</if>"
                "<if test=\"createdAfter != null\">AND created_at &gt;= #{createdAfter}</if></where> ORDER BY created_at DESC"
            ),
            "dynamicFeatures": ["WHERE", "IF"],
            "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.dynamic_template.present)
        self.assertEqual(model.dynamic_template.capability_profile.shape_family, "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(model.dynamic_template.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.dynamic_template.capability_profile.patch_surface, "STATEMENT_BODY")
        self.assertEqual(model.dynamic_template.capability_profile.baseline_family, "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP")

    def test_build_rewrite_facts_model_captures_distinct_relaxation_boundary(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listDistinctUserStatuses#v10",
            "sql": "SELECT DISTINCT status FROM users ORDER BY status",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.user.advanced",
            "statementId": "listDistinctUserStatuses",
            "templateSql": "SELECT DISTINCT status FROM users ORDER BY status",
            "dynamicFeatures": [],
        }
        equivalence = {
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "PARTIAL"}],
        }
        semantic_equivalence = {
            "status": "FAIL",
            "confidence": "HIGH",
            "evidenceLevel": "DB_FINGERPRINT",
            "hardConflicts": ["SEMANTIC_ROW_COUNT_MISMATCH", "SEMANTIC_FINGERPRINT_MISMATCH"],
        }

        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT status FROM users ORDER BY status",
            {},
            equivalence,
            semantic_equivalence,
        )

        self.assertTrue(model.aggregation_query.present)
        self.assertTrue(model.aggregation_query.distinct_present)
        self.assertTrue(model.aggregation_query.distinct_relaxation_candidate)
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "DISTINCT")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "DISTINCT_RELAXATION")
        self.assertEqual(model.aggregation_query.capability_profile.review_only_family, "DISTINCT_REVIEW_ONLY")
        self.assertEqual(model.aggregation_query.projection_expressions, ["status"])
        self.assertEqual(model.aggregation_query.order_by_expression, "status")
        self.assertEqual(model.aggregation_query.blockers, ["DISTINCT_PRESENT"])

    def test_build_rewrite_facts_model_captures_group_by_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.aggregateOrdersByStatus#v5",
            "sql": "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "aggregateOrdersByStatus",
            "templateSql": "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            {},
            {},
            {"status": "FAIL", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.present)
        self.assertTrue(model.aggregation_query.group_by_present)
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "GROUP_BY")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "GROUP_BY_AGGREGATION")
        self.assertEqual(model.aggregation_query.capability_profile.review_only_family, "GROUP_BY_REVIEW_ONLY")
        self.assertEqual(model.aggregation_query.group_by_columns, ["status"])
        self.assertEqual(model.aggregation_query.aggregate_functions, ["COUNT", "SUM"])
        self.assertEqual(model.aggregation_query.order_by_expression, "status")
        self.assertIn("GROUP_BY_PRESENT", model.aggregation_query.blockers)

    def test_build_rewrite_facts_model_captures_having_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.listOrderUserCountsHaving#v8",
            "sql": "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "listOrderUserCountsHaving",
            "templateSql": "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            {},
            {},
            {"status": "FAIL", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.group_by_present)
        self.assertTrue(model.aggregation_query.having_present)

    def test_build_rewrite_facts_model_detects_group_by_from_alias_cleanup_safe_baseline(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.aggregateOrdersByStatusAliased#v11",
            "sql": "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount FROM orders o GROUP BY o.status ORDER BY o.status",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "aggregateOrdersByStatusAliased",
            "templateSql": "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount FROM orders o GROUP BY o.status ORDER BY o.status",
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_COUNT", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.present)
        self.assertTrue(model.aggregation_query.group_by_present)
        self.assertEqual(model.aggregation_query.capability_profile.safe_baseline_family, "GROUP_BY_FROM_ALIAS_CLEANUP")
        self.assertEqual(model.aggregation_query.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "GROUP_BY")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "SAFE_BASELINE")
        self.assertIsNone(model.aggregation_query.capability_profile.review_only_family)
        self.assertIsNone(model.aggregation_query.having_expression)
        self.assertEqual(model.aggregation_query.aggregate_functions, ["COUNT", "SUM"])
        self.assertIn("GROUP_BY_PRESENT", model.aggregation_query.blockers)

    def test_build_rewrite_facts_model_detects_group_by_having_from_alias_cleanup_safe_baseline(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.listOrderUserCountsHavingAliased#v12",
            "sql": "SELECT o.user_id AS user_id, COUNT(*) AS total FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "listOrderUserCountsHavingAliased",
            "templateSql": "SELECT o.user_id AS user_id, COUNT(*) AS total FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id",
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_COUNT", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.present)
        self.assertTrue(model.aggregation_query.group_by_present)
        self.assertTrue(model.aggregation_query.having_present)
        self.assertEqual(model.aggregation_query.group_by_columns, ["o.user_id"])
        self.assertEqual(model.aggregation_query.having_expression, "COUNT(*) > 1")
        self.assertEqual(model.aggregation_query.aggregate_functions, ["COUNT"])
        self.assertEqual(model.aggregation_query.capability_profile.safe_baseline_family, "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP")
        self.assertEqual(model.aggregation_query.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "SAFE_BASELINE")

    def test_build_rewrite_facts_model_captures_having_wrapper_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.listOrderUserCountsHavingWrapped#v10",
            "sql": (
                "SELECT user_id, COUNT(*) AS total "
                "FROM ( SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ) oh "
                "ORDER BY user_id"
            ),
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "listOrderUserCountsHavingWrapped",
            "templateSql": (
                "SELECT user_id, COUNT(*) AS total "
                "FROM ( SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ) oh "
                "ORDER BY user_id"
            ),
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            {},
            {},
            {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.group_by_present)
        self.assertTrue(model.aggregation_query.having_present)
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "HAVING")
        self.assertEqual(model.aggregation_query.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(model.aggregation_query.capability_profile.safe_baseline_family, "REDUNDANT_HAVING_WRAPPER")
        self.assertTrue(model.aggregation_query.capability_profile.wrapper_flatten_candidate)
        self.assertEqual(model.aggregation_query.group_by_columns, ["user_id"])
        self.assertEqual(model.aggregation_query.having_expression, "COUNT(*) > 1")
        self.assertEqual(model.aggregation_query.aggregate_functions, ["COUNT"])
        self.assertEqual(model.aggregation_query.order_by_expression, "user_id")
        self.assertIn("GROUP_BY_PRESENT", model.aggregation_query.blockers)
        self.assertIn("HAVING_PRESENT", model.aggregation_query.blockers)

    def test_build_rewrite_facts_model_captures_window_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.listOrderAmountWindowRanks#v7",
            "sql": "SELECT order_no, amount, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS row_rank FROM orders",
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.order.harness",
            "statementId": "listOrderAmountWindowRanks",
            "templateSql": "SELECT order_no, amount, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS row_rank FROM orders",
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT order_no, amount FROM orders",
            {},
            {},
            {"status": "FAIL", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.window_present)
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "WINDOW")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "WINDOW_AGGREGATION")
        self.assertEqual(model.aggregation_query.window_functions, ["ROW_NUMBER"])
        self.assertIsNone(model.aggregation_query.order_by_expression)
        self.assertIn("WINDOW_PRESENT", model.aggregation_query.blockers)

    def test_build_rewrite_facts_model_captures_union_shape(self) -> None:
        sql_unit = {
            "sqlKey": "demo.shipment.harness.listShipmentStatusUnion#v6",
            "sql": (
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
            ),
            "xmlPath": "/tmp/demo_mapper.xml",
            "namespace": "demo.shipment.harness",
            "statementId": "listShipmentStatusUnion",
            "templateSql": (
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
            ),
            "dynamicFeatures": [],
        }
        model = build_rewrite_facts_model(
            sql_unit,
            "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED'",
            {},
            {},
            {"status": "FAIL", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
        )

        self.assertTrue(model.aggregation_query.union_present)
        self.assertEqual(model.aggregation_query.capability_profile.shape_family, "UNION")
        self.assertEqual(model.aggregation_query.capability_profile.constraint_family, "UNION_AGGREGATION")
        self.assertEqual(model.aggregation_query.union_branches, 2)
        self.assertEqual(model.aggregation_query.order_by_expression, "status, id")
        self.assertIn("UNION_PRESENT", model.aggregation_query.blockers)


if __name__ == "__main__":
    unittest.main()
