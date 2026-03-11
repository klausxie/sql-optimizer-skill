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


if __name__ == "__main__":
    unittest.main()
