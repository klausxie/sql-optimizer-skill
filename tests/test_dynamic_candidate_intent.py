from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.dynamic_candidate_intent_engine import assess_dynamic_candidate_intent_model
from sqlopt.platforms.sql.rewrite_facts import build_rewrite_facts_model


class DynamicCandidateIntentTest(unittest.TestCase):
    def test_dynamic_count_wrapper_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_count_wrapper_") as td:
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
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                rewrite_facts,
            )

        self.assertEqual(rewrite_facts.dynamic_template.capability_profile.shape_family, "IF_GUARDED_COUNT_WRAPPER")
        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)
        self.assertIn("<where>", str(assessment.rebuilt_template))
        self.assertIn("SELECT COUNT(*) FROM users", str(assessment.rebuilt_template))

    def test_dynamic_count_wrapper_accepts_count_one_candidate_as_template_preserving(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_count_wrapper_count1_") as td:
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
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                rewrite_facts,
            )

        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)

    def test_static_include_statement_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_intent_") as td:
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
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v13",
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
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                rewrite_facts,
            )

        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertIn("<include refid=\"AdvancedUserColumns\" />", str(assessment.rebuilt_template))

    def test_static_include_paged_wrapper_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_intent_paged_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <sql id="AdvancedUserColumns">id, name, email, status, created_at, updated_at</sql>
  <select id="listUsersRecentPagedWrapped">
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT <include refid="AdvancedUserColumns" />
      FROM users
    ) recent_users
    ORDER BY created_at DESC
    LIMIT 100
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersRecentPagedWrapped#v16",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( "
                    "SELECT id, name, email, status, created_at, updated_at FROM users ) recent_users "
                    "ORDER BY created_at DESC LIMIT 100"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersRecentPagedWrapped",
                "templateSql": (
                    'SELECT id, name, email, status, created_at, updated_at FROM ( '
                    'SELECT <include refid="AdvancedUserColumns" /> FROM users ) recent_users '
                    "ORDER BY created_at DESC LIMIT 100"
                ),
                "dynamicFeatures": ["INCLUDE"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
                },
                "includeBindings": [{"ref": "demo.user.advanced.AdvancedUserColumns", "properties": [], "bindingHash": "base"}],
            }
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
                rewrite_facts,
            )

        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)
        self.assertIn("<include refid=\"AdvancedUserColumns\" />", str(assessment.rebuilt_template))
        self.assertIn("LIMIT 100", str(assessment.rebuilt_template))

    def test_static_include_statement_rejects_fragment_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_intent_unsafe_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <sql id="AdvancedUserColumns">id, name</sql>
  <select id="listUsersViaStaticIncludeWrapped">
    SELECT id, name
    FROM (
      SELECT <include refid="AdvancedUserColumns" />
      FROM users
    ) u
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v13",
                "sql": "SELECT id, name FROM ( SELECT id, name FROM users ) u",
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersViaStaticIncludeWrapped",
                "templateSql": 'SELECT id, name FROM ( SELECT <include refid="AdvancedUserColumns" /> FROM users ) u',
                "dynamicFeatures": ["INCLUDE"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.advanced.AdvancedUserColumns", "dynamicFeatures": []}],
                },
            }
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email FROM users",
                {},
                {},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "STRUCTURE", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email FROM users",
                rewrite_facts,
            )

        self.assertEqual(assessment.intent, "UNSAFE_DYNAMIC_REWRITE")
        self.assertEqual(assessment.blocking_reason, "NO_TEMPLATE_PRESERVING_INTENT")

    def test_dynamic_filter_select_list_cleanup_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_filter_select_cleanup_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="listUsersFilteredAliased">
    SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at
    FROM users
    <where>
      <if test="status != null and status != ''">
        AND status = #{status}
      </if>
      <if test="createdAfter != null">
        AND created_at &gt;= #{createdAfter}
      </if>
    </where>
    ORDER BY created_at DESC
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersFilteredAliased#v17",
                "sql": (
                    "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                    "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersFilteredAliased",
                "templateSql": (
                    "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                    "FROM users <where> <if test=\"status != null and status != ''\"> AND status = #{status} </if> "
                    "<if test=\"createdAfter != null\"> AND created_at &gt;= #{createdAfter} </if> </where> ORDER BY created_at DESC"
                ),
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            }
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                rewrite_facts,
            )

        self.assertEqual(rewrite_facts.dynamic_template.capability_profile.baseline_family, "DYNAMIC_FILTER_SELECT_LIST_CLEANUP")
        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)
        self.assertIn("<where>", str(assessment.rebuilt_template))
        self.assertNotIn("id AS id", str(assessment.rebuilt_template))

    def test_dynamic_filter_from_alias_cleanup_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_filter_from_alias_cleanup_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="listUsersFilteredTableAliased">
    SELECT id, name, email, status, created_at, updated_at
    FROM users u
    <where>
      <if test="status != null and status != ''">
        AND status = #{status}
      </if>
      <if test="createdAfter != null">
        AND created_at &gt;= #{createdAfter}
      </if>
    </where>
    ORDER BY created_at DESC
  </select>
</mapper>""",
                encoding="utf-8",
            )
            sql_unit = {
                "sqlKey": "demo.user.advanced.listUsersFilteredTableAliased#v18",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users u WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersFilteredTableAliased",
                "templateSql": (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users u <where> <if test=\"status != null and status != ''\"> AND status = #{status} </if> "
                    "<if test=\"createdAfter != null\"> AND created_at &gt;= #{createdAfter} </if> </where> ORDER BY created_at DESC"
                ),
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            }
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                rewrite_facts,
            )

        self.assertEqual(rewrite_facts.dynamic_template.capability_profile.baseline_family, "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP")
        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)
        self.assertIn("FROM users <where>", str(assessment.rebuilt_template))
        self.assertNotIn("FROM users u", str(assessment.rebuilt_template))

    def test_dynamic_filter_wrapper_matches_template_preserving_edit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dynamic_filter_wrapper_") as td:
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
            }
            rewrite_facts = build_rewrite_facts_model(
                sql_unit,
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                {},
                {"evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}]},
                {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT", "hardConflicts": []},
            )

            assessment = assess_dynamic_candidate_intent_model(
                sql_unit,
                str(sql_unit["sql"]),
                "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
                rewrite_facts,
            )

        self.assertEqual(rewrite_facts.dynamic_template.capability_profile.shape_family, "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(rewrite_facts.dynamic_template.capability_profile.capability_tier, "SAFE_BASELINE")
        self.assertEqual(assessment.intent, "TEMPLATE_PRESERVING_STATEMENT_EDIT")
        self.assertTrue(assessment.template_preserving)
        self.assertTrue(assessment.template_effective_change)
        self.assertIn("<where>", str(assessment.rebuilt_template))
        self.assertIn("FROM users", str(assessment.rebuilt_template))
