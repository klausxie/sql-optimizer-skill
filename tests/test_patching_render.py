from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages import patching_render


class PatchingRenderTest(unittest.TestCase):
    def test_build_template_with_preserved_includes_keeps_include_tag(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patching_render_") as td:
            mapper = Path(td) / "demo_mapper.xml"
            mapper.write_text(
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
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "templateSql": 'SELECT * FROM users <include refid="BaseWhere" />',
                "xmlPath": str(mapper),
            }

            rebuilt, error = patching_render.build_template_with_preserved_includes(
                sql_unit,
                "SELECT * FROM users WHERE status = #{status}",
                "SELECT id, name FROM users WHERE status = #{status}",
            )

        self.assertIsNone(error)
        self.assertEqual(rebuilt, 'SELECT id, name FROM users <include refid="BaseWhere" />')

    def test_build_template_with_preserved_includes_rejects_changed_fragment_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patching_render_change_") as td:
            mapper = Path(td) / "demo_mapper.xml"
            mapper.write_text(
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
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "templateSql": 'SELECT * FROM users <include refid="BaseWhere" />',
                "xmlPath": str(mapper),
            }

            rebuilt, error = patching_render.build_template_with_preserved_includes(
                sql_unit,
                "SELECT * FROM users WHERE status = #{status}",
                "SELECT id, name FROM users WHERE active = TRUE",
            )

        self.assertIsNone(rebuilt)
        self.assertEqual(error, "included fragment content changed")

    def test_build_range_patch_supports_line_column_range(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patching_range_") as td:
            mapper = Path(td) / "demo_mapper.xml"
            mapper.write_text(
                "<select id=\"demo\">\n  SELECT *\n</select>\n",
                encoding="utf-8",
            )

            patch_text, changed_lines = patching_render.build_range_patch(
                mapper,
                {
                    "startLine": 2,
                    "startColumn": 3,
                    "endLine": 2,
                    "endColumn": 11,
                },
                "SELECT id",
            )

        self.assertIsNotNone(patch_text)
        self.assertGreater(changed_lines, 0)
        self.assertIn("+  SELECT id", patch_text)

    def test_build_unified_patch_returns_none_when_statement_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patching_unified_") as td:
            mapper = Path(td) / "demo_mapper.xml"
            mapper.write_text("<mapper><select id=\"a\">SELECT 1</select></mapper>\n", encoding="utf-8")

            patch_text, changed_lines = patching_render.build_unified_patch(mapper, "missing", "select", "SELECT 2")

        self.assertIsNone(patch_text)
        self.assertEqual(changed_lines, 0)


if __name__ == "__main__":
    unittest.main()
