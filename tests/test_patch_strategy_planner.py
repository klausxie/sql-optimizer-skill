from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.patch_strategy_planner import plan_patch_strategy


class PatchStrategyPlannerTest(unittest.TestCase):
    def test_wrapper_collapse_strategy_is_selected_for_static_count_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_wrapper_") as td:
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
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [
                    {"source": "DB_FINGERPRINT", "match_strength": "EXACT"},
                ],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            }

            rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                "SELECT COUNT(*) FROM users",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertTrue(rewrite_facts["wrapperQuery"]["collapsible"])
        self.assertIsNone(dynamic_intent)
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(candidates[0]["strategyType"], "SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(materialization["replayContract"]["replayMode"], "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(materialization["replayContract"]["requiredTemplateOps"], ["replace_statement_body"])
        self.assertEqual(materialization["replayContract"]["expectedRenderedSqlNormalized"], "SELECT COUNT(*) FROM users")
        self.assertEqual(ops[0]["op"], "replace_statement_body")
        self.assertEqual(ops[0]["afterTemplate"], "SELECT COUNT(*) FROM users")

    def test_wrapper_collapse_is_blocked_for_group_by_inner_query(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_groupby_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="userBaseQuery">SELECT status, count(*) FROM users GROUP BY status</sql>
  <select id="countUser">select count(1) from (<include refid="userBaseQuery" />) tmp</select>
</mapper>""",
                encoding="utf-8",
            )
            base_ref = f"{xml_path.resolve()}::demo.user.userBaseQuery"
            sql_unit = {
                "sqlKey": "demo.user.countUser#v2",
                "sql": "select count(1) from ( SELECT status, count(*) FROM users GROUP BY status ) tmp",
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
                    "templateSql": "SELECT status, count(*) FROM users GROUP BY status",
                    "dynamicFeatures": [],
                    "includeBindings": [],
                },
            }
            equivalence = {"checked": True, "method": "sql_semantic_compare_v2", "rowCount": {"status": "MATCH"}}
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidence": {"fingerprintStrength": "EXACT"},
                "hardConflicts": [],
            }

            rewrite_facts, dynamic_intent, patchability, selected, _candidates, materialization, _ops = plan_patch_strategy(
                sql_unit,
                "SELECT COUNT(*) FROM users GROUP BY status",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertFalse(rewrite_facts["wrapperQuery"]["collapsible"])
        self.assertIsNone(dynamic_intent)
        self.assertIn("GROUP_BY_PRESENT", rewrite_facts["wrapperQuery"]["blockers"])
        self.assertNotEqual(selected, {"strategyType": "SAFE_WRAPPER_COLLAPSE"})
        self.assertNotEqual(materialization.get("mode"), "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE")

    def test_exact_template_edit_is_selected_for_simple_cte_inline(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listRecentUsersViaCte#v11",
            "sql": (
                "WITH recent_users AS ( SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE created_at >= #{createdAfter} ) "
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM recent_users ORDER BY created_at DESC LIMIT 20"
            ),
            "xmlPath": str(Path(__file__).resolve()),
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
            "checked": True,
            "method": "sql_semantic_compare_v2",
            "rowCount": {"status": "MATCH"},
            "keySetHash": {"status": "MATCH"},
            "rowSampleHash": {"status": "MATCH"},
            "evidenceRefs": [],
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
        }
        semantic_equivalence = {
            "status": "PASS",
            "confidence": "HIGH",
            "evidenceLevel": "DB_FINGERPRINT",
            "hardConflicts": [],
            "evidence": {"fingerprintStrength": "EXACT"},
        }

        rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
            sql_unit,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
            {},
            equivalence,
            semantic_equivalence,
            enable_fragment_materialization=False,
        )

        self.assertTrue(rewrite_facts["cteQuery"]["collapsible"])
        self.assertTrue(rewrite_facts["cteQuery"]["inlineCandidate"])
        self.assertIsNone(dynamic_intent)
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "EXACT_TEMPLATE_EDIT")
        self.assertEqual(candidates[0]["strategyType"], "EXACT_TEMPLATE_EDIT")
        self.assertEqual(materialization["mode"], "STATEMENT_SQL")
        self.assertEqual(materialization["targetType"], "STATEMENT")
        self.assertEqual(materialization["replayContract"]["replayMode"], "STATEMENT_SQL")
        self.assertEqual(
            materialization["replayContract"]["expectedRenderedSqlNormalized"],
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
        )
        self.assertEqual(ops, [])

    def test_planner_records_aggregation_constraint_blocked_hint(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.advanced.listDistinctUserStatuses#v10",
            "sql": "SELECT DISTINCT status FROM users ORDER BY status",
            "xmlPath": str(Path(__file__).resolve()),
            "namespace": "demo.user.advanced",
            "statementId": "listDistinctUserStatuses",
            "templateSql": "SELECT DISTINCT status FROM users ORDER BY status",
            "dynamicFeatures": [],
        }
        equivalence = {
            "checked": True,
            "method": "sql_semantic_compare_v2",
            "rowCount": {"status": "MATCH"},
            "keySetHash": {"status": "MISMATCH"},
            "rowSampleHash": {"status": "MISMATCH"},
            "evidenceRefs": [],
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "PARTIAL"}],
        }
        semantic_equivalence = {
            "status": "PASS",
            "confidence": "HIGH",
            "evidenceLevel": "DB_COUNT",
            "hardConflicts": [],
            "evidence": {"fingerprintStrength": "PARTIAL"},
        }

        rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
            sql_unit,
            "SELECT status FROM users ORDER BY status",
            {},
            equivalence,
            semantic_equivalence,
            enable_fragment_materialization=False,
        )

        self.assertTrue(rewrite_facts["aggregationQuery"]["distinctRelaxationCandidate"])
        self.assertIsNone(dynamic_intent)
        self.assertFalse(patchability["eligible"])
        self.assertEqual(patchability["aggregationConstraintFamily"], "DISTINCT_RELAXATION")
        self.assertEqual(patchability["aggregationCapabilityTier"], "REVIEW_REQUIRED")
        self.assertIsNone(selected)
        self.assertEqual(candidates[0]["reasonCode"], "AGGREGATION_CONSTRAINT_BLOCKED")
        self.assertEqual(candidates[0]["aggregationConstraintFamily"], "DISTINCT_RELAXATION")
        self.assertEqual(candidates[0]["blockedBy"], "AGGREGATION_CONSTRAINT")
        self.assertEqual(materialization["mode"], "STATEMENT_SQL")
        self.assertEqual(ops, [])

    def test_planner_records_dynamic_constraint_blocked_hint(self) -> None:
        sql_unit = {
            "sqlKey": "demo.order.harness.findOrdersByNos#v1",
            "sql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            "xmlPath": str(Path(__file__).resolve()),
            "namespace": "demo.order.harness",
            "statementId": "findOrdersByNos",
            "templateSql": "SELECT <include refid=\"OrderColumns\" /> FROM orders <where><foreach>#{orderNo}</foreach></where>",
            "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
            "dynamicTrace": {
                "statementFeatures": ["INCLUDE", "WHERE", "FOREACH"],
                "includeFragments": [{"ref": "demo.order.harness.OrderColumns", "dynamicFeatures": []}],
            },
        }
        equivalence = {
            "checked": True,
            "method": "sql_semantic_compare_v2",
            "rowCount": {"status": "MATCH"},
            "keySetHash": {"status": "MATCH"},
            "rowSampleHash": {"status": "MATCH"},
            "evidenceRefs": [],
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
        }
        semantic_equivalence = {
            "status": "PASS",
            "confidence": "HIGH",
            "evidenceLevel": "DB_FINGERPRINT",
            "hardConflicts": [],
            "evidence": {"fingerprintStrength": "EXACT"},
        }

        rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
            sql_unit,
            "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            {},
            equivalence,
            semantic_equivalence,
            enable_fragment_materialization=False,
        )

        self.assertEqual(rewrite_facts["dynamicTemplate"]["capabilityProfile"]["shapeFamily"], "FOREACH_IN_PREDICATE")
        self.assertEqual(dynamic_intent["intent"], "UNSAFE_DYNAMIC_REWRITE")
        self.assertFalse(patchability["eligible"])
        self.assertEqual(patchability["dynamicShapeFamily"], "FOREACH_IN_PREDICATE")
        self.assertEqual(patchability["dynamicCapabilityTier"], "REVIEW_REQUIRED")
        self.assertEqual(patchability["dynamicBlockingReason"], "FOREACH_INCLUDE_PREDICATE")
        self.assertIsNone(selected)
        self.assertEqual(candidates[0]["reasonCode"], "DYNAMIC_TEMPLATE_CONSTRAINT_BLOCKED")
        self.assertEqual(candidates[0]["dynamicShapeFamily"], "FOREACH_IN_PREDICATE")
        self.assertEqual(candidates[0]["dynamicBlockingReason"], "FOREACH_INCLUDE_PREDICATE")
        self.assertEqual(materialization["mode"], "UNMATERIALIZABLE")
        self.assertEqual(ops, [])

    def test_dynamic_statement_strategy_is_selected_for_static_include_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_dynamic_stmt_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <sql id="AdvancedUserColumns">id, name, email, status, created_at, updated_at</sql>
  <select id="listUsersViaStaticIncludeWrapped">
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT <include refid="AdvancedUserColumns" />
      FROM users
    ) u
    ORDER BY created_at DESC
  </select>
</mapper>""",
                encoding="utf-8",
            )
            content = xml_path.read_text(encoding="utf-8")
            body = """
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT <include refid="AdvancedUserColumns" />
      FROM users
    ) u
    ORDER BY created_at DESC
  """
            start = content.index(body)
            end = start + len(body)
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v13",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( SELECT id, name, email, status, created_at, updated_at FROM users ) u "
                    "ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersViaStaticIncludeWrapped",
                "templateSql": 'SELECT id, name, email, status, created_at, updated_at FROM ( SELECT <include refid="AdvancedUserColumns" /> FROM users ) u ORDER BY created_at DESC',
                "dynamicFeatures": ["INCLUDE"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
                },
                "includeBindings": [{"ref": "demo.user.advanced.AdvancedUserColumns", "properties": [], "bindingHash": "base"}],
                "locators": {"statementId": "listUsersViaStaticIncludeWrapped", "range": {"startOffset": start, "endOffset": end}},
            }
            equivalence = {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            }

            rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                {},
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertEqual(rewrite_facts["dynamicTemplate"]["capabilityProfile"]["shapeFamily"], "STATIC_INCLUDE_ONLY")
        self.assertEqual(dynamic_intent["intent"], "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(patchability["eligible"])
        self.assertIn("DYNAMIC_STATEMENT_CANONICAL_EDIT", patchability["allowedCapabilities"])
        self.assertEqual(selected["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(candidates[0]["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertEqual(ops[0]["op"], "replace_statement_body")
        self.assertIn("<include refid=\"AdvancedUserColumns\" />", ops[0]["afterTemplate"])

    def test_dynamic_statement_strategy_is_selected_for_dynamic_count_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_dynamic_count_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="countUsersFilteredWrapped">
    SELECT COUNT(1)
    FROM (
      SELECT id
      FROM users
      <where>
        <if test="status != null and status != ''">
          AND status = #{status}
        </if>
        <if test="createdAfter != null">
          AND created_at &gt;= #{createdAfter}
        </if>
      </where>
    ) filtered_users
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.advanced.countUsersFilteredWrapped#v14",
                "sql": "SELECT COUNT(1) FROM ( SELECT id FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ) filtered_users",
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "countUsersFilteredWrapped",
                "templateSql": (
                    "SELECT COUNT(1) FROM ( SELECT id FROM users <where> <if test=\"status != null and status != ''\"> "
                    "AND status = #{status} </if> <if test=\"createdAfter != null\"> AND created_at &gt;= #{createdAfter} "
                    "</if> </where> ) filtered_users"
                ),
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            }
            equivalence = {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            }

            rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                {},
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertEqual(rewrite_facts["dynamicTemplate"]["capabilityProfile"]["shapeFamily"], "IF_GUARDED_COUNT_WRAPPER")
        self.assertEqual(dynamic_intent["intent"], "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(dynamic_intent["templateEffectiveChange"])
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(candidates[0]["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertEqual(ops[0]["op"], "replace_statement_body")
        self.assertIn("<where>", ops[0]["afterTemplate"])
        self.assertIn("SELECT COUNT(*) FROM users", ops[0]["afterTemplate"])

    def test_dynamic_statement_strategy_is_selected_when_template_changes_but_sql_is_effectively_same(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_dynamic_same_sql_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            content = """<mapper namespace="demo.user.advanced">
  <sql id="AdvancedUserColumns">id, name, email, status, created_at, updated_at</sql>
  <select id="listUsersViaStaticIncludeWrapped">
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT <include refid="AdvancedUserColumns" />
      FROM users
    ) u
    ORDER BY created_at DESC
  </select>
</mapper>"""
            xml_path.write_text(content, encoding="utf-8")
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( SELECT id, name, email, status, created_at, updated_at FROM users ) u "
                    "ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersViaStaticIncludeWrapped",
                "templateSql": (
                    'SELECT id, name, email, status, created_at, updated_at FROM ( SELECT <include refid="AdvancedUserColumns" /> FROM users ) u ORDER BY created_at DESC'
                ),
                "dynamicFeatures": ["INCLUDE"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
                },
                "includeBindings": [{"ref": "demo.user.advanced.AdvancedUserColumns", "properties": [], "bindingHash": "base"}],
            }
            equivalence = {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            }

            rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                str(sql_unit["sql"]),
                {},
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertTrue(rewrite_facts["effectiveChange"])
        self.assertEqual(dynamic_intent["intent"], "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(dynamic_intent["templateEffectiveChange"])
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(candidates[0]["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")

    def test_dynamic_statement_strategy_is_selected_for_dynamic_filter_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patch_strategy_dynamic_filter_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="listUsersFilteredWrapped">
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT id, name, email, status, created_at, updated_at
      FROM users
      <where>
        <if test="status != null and status != ''">
          AND status = #{status}
        </if>
        <if test="createdAfter != null">
          AND created_at &gt;= #{createdAfter}
        </if>
      </where>
    ) filtered_users
    ORDER BY created_at DESC
  </select>
</mapper>""",
                encoding="utf-8",
            )
            content = xml_path.read_text(encoding="utf-8")
            start = content.index("<select id=\"listUsersFilteredWrapped\"")
            end = content.index("</select>", start) + len("</select>")
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersFilteredWrapped#v15",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( "
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "WHERE status = #{status} AND created_at >= #{createdAfter} "
                    ") filtered_users ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersFilteredWrapped",
                "templateSql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( "
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "<where> <if test=\"status != null and status != ''\"> AND status = #{status} </if> "
                    "<if test=\"createdAfter != null\"> AND created_at &gt;= #{createdAfter} </if> </where> "
                    ") filtered_users ORDER BY created_at DESC"
                ),
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
                "locators": {"statementId": "listUsersFilteredWrapped", "range": {"startOffset": start, "endOffset": end}},
            }
            equivalence = {
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            }
            semantic_equivalence = {
                "status": "PASS",
                "confidence": "HIGH",
                "evidenceLevel": "DB_FINGERPRINT",
                "hardConflicts": [],
                "evidence": {"fingerprintStrength": "EXACT"},
            }

            rewrite_facts, dynamic_intent, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                {},
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertEqual(rewrite_facts["dynamicTemplate"]["capabilityProfile"]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(rewrite_facts["dynamicTemplate"]["capabilityProfile"]["capabilityTier"], "SAFE_BASELINE")
        self.assertEqual(dynamic_intent["intent"], "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(dynamic_intent["templateEffectiveChange"])
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(candidates[0]["strategyType"], "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertEqual(ops[0]["op"], "replace_statement_body")
        self.assertIn("<where>", ops[0]["afterTemplate"])
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertEqual(ops[0]["op"], "replace_statement_body")


if __name__ == "__main__":
    unittest.main()
