from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.stages import patching_templates


class PatchingTemplatesTest(unittest.TestCase):
    def test_build_template_plan_patch_requires_replay_verification(self) -> None:
        patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
            {"locators": {"range": {"startOffset": 0, "endOffset": 1}}},
            {
                "rewriteMaterialization": {"mode": "STATEMENT_TEMPLATE_SAFE", "replayVerified": False},
                "templateRewriteOps": [{"op": "replace_statement_body", "afterTemplate": "SELECT 1"}],
            },
            Path("."),
        )

        self.assertIsNone(patch_text)
        self.assertEqual(changed_lines, 0)
        self.assertEqual(error["code"], "PATCH_TEMPLATE_MATERIALIZATION_MISSING")

    def test_build_template_plan_patch_ignores_non_template_safe_mode(self) -> None:
        patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
            {},
            {"rewriteMaterialization": {"mode": "UNSAFE", "replayVerified": True}},
            Path("."),
        )

        self.assertIsNone(patch_text)
        self.assertEqual(changed_lines, 0)
        self.assertIsNone(error)

    def test_build_template_plan_patch_rejects_missing_replay_contract_ops(self) -> None:
        patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
            {"locators": {"range": {"startOffset": 0, "endOffset": 1}}},
            {
                "rewriteMaterialization": {
                    "mode": "STATEMENT_TEMPLATE_SAFE",
                    "replayVerified": True,
                    "replayContract": {"requiredTemplateOps": ["replace_fragment_body"]},
                },
                "templateRewriteOps": [{"op": "replace_statement_body", "afterTemplate": "SELECT 1"}],
            },
            Path("."),
        )

        self.assertIsNone(patch_text)
        self.assertEqual(changed_lines, 0)
        self.assertEqual(error["code"], "PATCH_TEMPLATE_MATERIALIZATION_MISSING")

    def test_build_template_plan_patch_builds_fragment_patch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_template_fragment_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
</mapper>""",
                encoding="utf-8",
            )
            fragment_body = "WHERE status = #{status}"
            start = mapper.read_text(encoding="utf-8").index(fragment_body)
            end = start + len(fragment_body)
            fragment_key = f"{mapper.resolve()}::demo.user.BaseWhere"
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "fragments.jsonl").write_text(
                json.dumps(
                    {
                        "fragmentKey": fragment_key,
                        "xmlPath": str(mapper),
                        "locators": {"range": {"startOffset": start, "endOffset": end}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
                {},
                {
                    "rewriteMaterialization": {
                        "mode": "FRAGMENT_TEMPLATE_SAFE",
                        "targetRef": fragment_key,
                        "replayVerified": True,
                    },
                    "templateRewriteOps": [
                        {
                            "op": "replace_fragment_body",
                            "targetRef": fragment_key,
                            "afterTemplate": "WHERE status = #{status} AND active = TRUE",
                        }
                    ],
                },
                run_dir,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(patch_text)
        self.assertGreater(changed_lines, 0)
        self.assertIn("active = TRUE", patch_text)

    def test_build_template_plan_patch_builds_statement_patch_for_wrapper_collapse_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_template_stmt_wrapper_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <select id="countUser">select count(1) from (<include refid="userBaseQuery" />) tmp</select>
</mapper>""",
                encoding="utf-8",
            )
            statement_body = 'select count(1) from (<include refid="userBaseQuery" />) tmp'
            start = mapper.read_text(encoding="utf-8").index(statement_body)
            end = start + len(statement_body)
            patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
                {"xmlPath": str(mapper), "locators": {"range": {"startOffset": start, "endOffset": end}}},
                {
                    "rewriteMaterialization": {
                        "mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
                        "replayVerified": True,
                    },
                    "templateRewriteOps": [
                        {
                            "op": "replace_statement_body",
                            "afterTemplate": "SELECT COUNT(*) FROM users",
                        }
                    ],
                },
                run_dir,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(patch_text)
        self.assertGreater(changed_lines, 0)
        self.assertIn("SELECT COUNT(*) FROM users", patch_text)

    def test_build_template_plan_patch_builds_fragment_patch_for_auto_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_template_fragment_auto_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
</mapper>""",
                encoding="utf-8",
            )
            fragment_body = "WHERE status = #{status}"
            start = mapper.read_text(encoding="utf-8").index(fragment_body)
            end = start + len(fragment_body)
            fragment_key = f"{mapper.resolve()}::demo.user.BaseWhere"
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "fragments.jsonl").write_text(
                json.dumps(
                    {
                        "fragmentKey": fragment_key,
                        "xmlPath": str(mapper),
                        "locators": {"range": {"startOffset": start, "endOffset": end}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            patch_text, changed_lines, error = patching_templates.build_template_plan_patch(
                {},
                {
                    "rewriteMaterialization": {
                        "mode": "FRAGMENT_TEMPLATE_SAFE_AUTO",
                        "targetRef": fragment_key,
                        "replayVerified": True,
                    },
                    "templateRewriteOps": [
                        {
                            "op": "replace_fragment_body",
                            "targetRef": fragment_key,
                            "afterTemplate": "WHERE status = #{status} AND active = TRUE",
                        }
                    ],
                },
                run_dir,
            )

        self.assertIsNone(error)
        self.assertIsNotNone(patch_text)
        self.assertGreater(changed_lines, 0)
        self.assertIn("active = TRUE", patch_text)


if __name__ == "__main__":
    unittest.main()
