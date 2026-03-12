from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlopt.platforms.sql.template_rendering import (
    collect_fragments,
    render_fragment_body_sql,
    render_logical_text,
)


class TemplateRenderingTest(unittest.TestCase):
    def test_render_logical_text_applies_where_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template_render_where_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="countUsersDirectFiltered">
    SELECT COUNT(*)
    FROM users
    <where>
      <if test="status != null and status != ''">
        AND status = #{status}
      </if>
      <if test="createdAfter != null">
        AND created_at &gt;= #{createdAfter}
      </if>
    </where>
  </select>
</mapper>""",
                encoding="utf-8",
            )
            root = ET.parse(xml_path).getroot()
            statement = next(iter(root))

            rendered = render_logical_text(
                statement,
                "demo.user.advanced",
                xml_path,
                collect_fragments(root, "demo.user.advanced", xml_path),
            )

        self.assertEqual(
            " ".join(rendered.split()),
            "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
        )

    def test_render_fragment_body_sql_applies_set_semantics(self) -> None:
        rendered = render_fragment_body_sql(
            """UPDATE users
            <set>
              <if test="name != null">name = #{name},</if>
              <if test="email != null">email = #{email},</if>
            </set>
            WHERE id = #{id}""",
            "demo.user.advanced",
            Path("/tmp/demo_mapper.xml"),
            {},
        )

        self.assertEqual(
            rendered,
            "UPDATE users SET name = #{name}, email = #{email} WHERE id = #{id}",
        )

    def test_render_logical_text_applies_choose_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="template_render_choose_") as td:
            xml_path = Path(td) / "demo_mapper.xml"
            xml_path.write_text(
                """<mapper namespace="demo.user.advanced">
  <select id="findUsersByKeyword">
    SELECT id, name
    FROM users
    <where>
      <choose>
        <when test="keyword != null and keyword != ''">
          name ILIKE #{keywordPattern}
        </when>
        <when test="status != null and status != ''">
          status = #{status}
        </when>
        <otherwise>
          status != 'DELETED'
        </otherwise>
      </choose>
    </where>
    ORDER BY created_at DESC
  </select>
</mapper>""",
                encoding="utf-8",
            )
            root = ET.parse(xml_path).getroot()
            statement = next(iter(root))

            rendered = render_logical_text(
                statement,
                "demo.user.advanced",
                xml_path,
                collect_fragments(root, "demo.user.advanced", xml_path),
            )

        self.assertEqual(
            " ".join(rendered.split()),
            "SELECT id, name FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC",
        )


if __name__ == "__main__":
    unittest.main()
