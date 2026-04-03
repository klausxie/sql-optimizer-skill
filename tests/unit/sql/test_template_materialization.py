from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.template_materializer import build_rewrite_materialization


class TemplateMaterializerTest(unittest.TestCase):
    def test_static_statement_defaults_to_statement_sql(self) -> None:
        sql_unit = {
            "sqlKey": "demo.user.listUsers",
            "sql": "SELECT * FROM users",
        }
        materialization, ops = build_rewrite_materialization(sql_unit, "SELECT id FROM users", {})
        self.assertEqual(materialization["mode"], "STATEMENT_SQL")
        self.assertEqual(materialization["targetType"], "STATEMENT")
        self.assertEqual(ops, [])

    def test_include_statement_can_materialize_template_when_replay_matches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tmpl_stmt_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded">
    SELECT * FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.findIncluded",
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "templateSql": 'SELECT * FROM users <include refid="BaseWhere" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": f"{xml_path.resolve()}::demo.user.BaseWhere", "properties": [], "bindingHash": "abc"}],
                "primaryFragmentTarget": f"{xml_path.resolve()}::demo.user.BaseWhere",
            }
            materialization, ops = build_rewrite_materialization(sql_unit, "SELECT id FROM users WHERE status = #{status}", {})
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertEqual(ops[0]["op"], "replace_statement_body")
        self.assertIn("SELECT id FROM users", ops[0]["afterTemplate"])
        self.assertIn("<include refid=\"BaseWhere\" />", ops[0]["afterTemplate"])

    def test_include_statement_escapes_xml_operators_in_text_segments(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tmpl_stmt_escape_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded">
    SELECT * FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.findIncluded",
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "xmlPath": str(xml_path),
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "templateSql": 'SELECT * FROM users <include refid="BaseWhere" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": f"{xml_path.resolve()}::demo.user.BaseWhere", "properties": [], "bindingHash": "abc"}],
                "primaryFragmentTarget": f"{xml_path.resolve()}::demo.user.BaseWhere",
            }
            materialization, ops = build_rewrite_materialization(
                sql_unit,
                "SELECT * FROM users WHERE status = #{status} AND score < 10",
                {},
            )
        self.assertEqual(materialization["mode"], "STATEMENT_TEMPLATE_SAFE")
        self.assertIn("&lt; 10", ops[0]["afterTemplate"])

    def test_static_fragment_can_auto_materialize_when_flag_disabled(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users WHERE status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [{"ref": target_ref, "properties": [], "bindingHash": "abc"}],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "WHERE status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users WHERE status = #{status} ORDER BY created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=False,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE_AUTO")
        self.assertEqual(materialization["targetRef"], target_ref)
        self.assertTrue(materialization["replayVerified"])
        self.assertFalse(materialization["featureFlagApplied"])
        self.assertEqual(ops[0]["op"], "replace_fragment_body")
        self.assertIn("ORDER BY created_at DESC", ops[0]["afterTemplate"])

    def test_dynamic_fragment_stays_disabled_when_flag_is_off(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users WHERE status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [{"ref": target_ref, "properties": [], "bindingHash": "abc"}],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "WHERE <if test='status != null'>status = #{status}</if>",
                "dynamicFeatures": ["IF"],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users WHERE status = #{status} ORDER BY created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=False,
        )
        self.assertEqual(materialization["mode"], "UNMATERIALIZABLE")
        self.assertEqual(materialization["reasonCode"], "FRAGMENT_MATERIALIZATION_DISABLED")
        self.assertEqual(ops, [])

    def test_static_fragment_can_materialize_when_flag_enabled(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users WHERE status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [{"ref": target_ref, "properties": [], "bindingHash": "abc"}],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "WHERE status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users WHERE status = #{status} ORDER BY created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertEqual(materialization["targetRef"], target_ref)
        self.assertEqual(ops[0]["op"], "replace_fragment_body")
        self.assertIn("ORDER BY created_at DESC", ops[0]["afterTemplate"])

    def test_static_fragment_escapes_xml_operators(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users WHERE status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [{"ref": target_ref, "properties": [], "bindingHash": "abc"}],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "xmlPath": "/tmp/x.xml",
                "namespace": "demo.user",
                "templateSql": "WHERE status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users WHERE status = #{status} AND score < 10",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertIn("&lt; 10", ops[0]["afterTemplate"])

    def test_nested_static_include_fragment_can_materialize_when_flag_enabled(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        nested_ref = "/tmp/x.xml::demo.user.BaseStatus"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users WHERE status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [{"ref": target_ref, "properties": [], "bindingHash": "abc"}],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "xmlPath": "/tmp/x.xml",
                "namespace": "demo.user",
                "templateSql": 'WHERE <include refid="BaseStatus" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [{"ref": nested_ref, "properties": [], "bindingHash": "nested"}],
            },
            nested_ref: {
                "fragmentKey": nested_ref,
                "xmlPath": "/tmp/x.xml",
                "namespace": "demo.user",
                "templateSql": "status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            },
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users WHERE status = #{status} ORDER BY created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertIn('<include refid="BaseStatus" />', ops[0]["afterTemplate"])
        self.assertIn("ORDER BY created_at DESC", ops[0]["afterTemplate"])

    def test_nested_static_include_fragment_with_binding_can_materialize(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        nested_ref = "/tmp/x.xml::demo.user.BaseStatus"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users u WHERE u.status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "u", "valueNormalized": "u"}],
                    "bindingHash": "abc",
                }
            ],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "xmlPath": "/tmp/x.xml",
                "namespace": "demo.user",
                "templateSql": 'WHERE <include refid="BaseStatus"><property name="alias" value="${alias}" /></include>',
                "dynamicFeatures": ["INCLUDE"],
                "includeBindings": [
                    {
                        "ref": nested_ref,
                        "properties": [{"name": "alias", "valueRaw": "${alias}", "valueNormalized": "${alias}"}],
                        "bindingHash": "nested",
                    }
                ],
            },
            nested_ref: {
                "fragmentKey": nested_ref,
                "xmlPath": "/tmp/x.xml",
                "namespace": "demo.user",
                "templateSql": "${alias}.status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            },
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users u WHERE u.status = #{status} ORDER BY u.created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertIn('<property name="alias" value="${alias}" />', ops[0]["afterTemplate"])
        self.assertIn("ORDER BY ${alias}.created_at DESC", ops[0]["afterTemplate"])

    def test_static_fragment_with_property_binding_can_materialize_when_flag_enabled(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users u WHERE u.status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "u", "valueNormalized": "u"}],
                    "bindingHash": "abc",
                }
            ],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "WHERE ${alias}.status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users u WHERE u.status = #{status} ORDER BY u.created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertEqual(materialization["reasonCode"], "STATIC_FRAGMENT_SAFE_WITH_BINDINGS")
        self.assertIn("${alias}.created_at", ops[0]["afterTemplate"])

    def test_static_fragment_with_repeated_identical_bindings_can_materialize(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users u WHERE u.status = #{status} OR EXISTS (SELECT 1 WHERE u.status = #{status})",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "u", "valueNormalized": "u"}],
                    "bindingHash": "same",
                },
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "u", "valueNormalized": "u"}],
                    "bindingHash": "same",
                },
            ],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "${alias}.status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users u WHERE u.status = #{status} ORDER BY u.created_at DESC OR EXISTS (SELECT 1 WHERE u.status = #{status} ORDER BY u.created_at DESC)",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "FRAGMENT_TEMPLATE_SAFE")
        self.assertTrue(materialization["replayVerified"])
        self.assertIn("${alias}.created_at", ops[0]["afterTemplate"])

    def test_static_fragment_with_mismatched_bindings_stays_unmaterializable(self) -> None:
        target_ref = "/tmp/x.xml::demo.user.BaseWhere"
        sql_unit = {
            "sqlKey": "demo.user.findIncluded",
            "sql": "SELECT * FROM users u WHERE u.status = #{status} OR SELECT * FROM users x WHERE x.status = #{status}",
            "dynamicFeatures": ["INCLUDE"],
            "includeBindings": [
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "u", "valueNormalized": "u"}],
                    "bindingHash": "u",
                },
                {
                    "ref": target_ref,
                    "properties": [{"name": "alias", "valueRaw": "x", "valueNormalized": "x"}],
                    "bindingHash": "x",
                },
            ],
            "primaryFragmentTarget": target_ref,
        }
        fragment_catalog = {
            target_ref: {
                "fragmentKey": target_ref,
                "templateSql": "${alias}.status = #{status}",
                "dynamicFeatures": [],
                "includeBindings": [],
            }
        }
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            "SELECT * FROM users u WHERE u.status = #{status} ORDER BY u.created_at DESC OR SELECT * FROM users x WHERE x.status = #{status} ORDER BY x.created_at DESC",
            fragment_catalog,
            enable_fragment_materialization=True,
        )
        self.assertEqual(materialization["mode"], "UNMATERIALIZABLE")
        self.assertEqual(materialization["reasonCode"], "MULTIPLE_FRAGMENT_BINDINGS_MISMATCH")
        self.assertEqual(ops, [])


if __name__ == "__main__":
    unittest.main()
