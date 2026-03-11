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

            rewrite_facts, patchability, selected, candidates, materialization, ops = plan_patch_strategy(
                sql_unit,
                "SELECT COUNT(*) FROM users",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertTrue(rewrite_facts["wrapperQuery"]["collapsible"])
        self.assertTrue(patchability["eligible"])
        self.assertEqual(selected["strategyType"], "SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(candidates[0]["strategyType"], "SAFE_WRAPPER_COLLAPSE")
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE")
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

            rewrite_facts, patchability, selected, _candidates, materialization, _ops = plan_patch_strategy(
                sql_unit,
                "SELECT COUNT(*) FROM users GROUP BY status",
                fragment_catalog,
                equivalence,
                semantic_equivalence,
                enable_fragment_materialization=False,
            )

        self.assertFalse(rewrite_facts["wrapperQuery"]["collapsible"])
        self.assertIn("GROUP_BY_PRESENT", rewrite_facts["wrapperQuery"]["blockers"])
        self.assertNotEqual(selected, {"strategyType": "SAFE_WRAPPER_COLLAPSE"})
        self.assertNotEqual(materialization.get("mode"), "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE")


if __name__ == "__main__":
    unittest.main()
