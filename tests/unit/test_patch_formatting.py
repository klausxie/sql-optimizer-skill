from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.patch_formatting import detect_duplicate_clause_in_template_ops
from sqlopt.stages.patch_formatting import format_sql_for_patch, format_template_ops_for_patch


class PatchFormattingTest(unittest.TestCase):
    def test_format_sql_for_patch_keeps_literals_and_adds_breaks(self) -> None:
        sql = "SELECT id, 'FROM users' AS note FROM users WHERE status = #{status} AND active = 1 ORDER BY created_at DESC"
        formatted = format_sql_for_patch(sql)
        self.assertIn("SELECT id", formatted)
        self.assertIn("'FROM users'", formatted)
        self.assertIn("AS note", formatted)
        self.assertIn("\nFROM users", formatted)
        self.assertIn("\nWHERE status = #{status}", formatted)
        self.assertIn("\n  AND active = 1", formatted)
        self.assertIn("\nORDER BY created_at DESC", formatted)

    def test_detect_duplicate_clause_in_template_ops(self) -> None:
        acceptance = {
            "templateRewriteOps": [
                {"afterTemplate": "SELECT id FROM users WHERE status = 1 WHERE active = 1 ORDER BY created_at DESC"}
            ]
        }
        duplicate = detect_duplicate_clause_in_template_ops(acceptance)
        self.assertEqual(duplicate, "WHERE")

    def test_format_template_ops_for_patch_aligns_statement_body_indentation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_formatting_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                "<mapper>\n  <select id=\"findUsers\">\n    SELECT * FROM users\n  </select>\n</mapper>\n",
                encoding="utf-8",
            )
            text = mapper.read_text(encoding="utf-8")
            target = "    SELECT * FROM users\n"
            start = text.index(target)
            end = start + len(target)

            sql_unit = {
                "xmlPath": str(mapper),
                "locators": {"range": {"startOffset": start, "endOffset": end}},
            }
            acceptance = {
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "afterTemplate": "SELECT id, name FROM users WHERE status = #{status} AND active = 1",
                    }
                ]
            }

            formatted = format_template_ops_for_patch(sql_unit, acceptance, run_dir)

        op = formatted["templateRewriteOps"][0]
        after = op["afterTemplate"]
        self.assertIn("\n    FROM users", after)
        self.assertIn("\n      AND active = 1", after)


if __name__ == "__main__":
    unittest.main()
