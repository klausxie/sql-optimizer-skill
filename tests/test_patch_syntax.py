from __future__ import annotations

import unittest

from sqlopt.verification.patch_artifact import PatchArtifactResult
from sqlopt.verification.patch_replay import ReplayResult
from sqlopt.verification.patch_syntax import verify_patch_syntax


class PatchSyntaxTest(unittest.TestCase):
    def test_verify_patch_syntax_rejects_obviously_invalid_sql(self) -> None:
        result = verify_patch_syntax(
            sql_unit={"xmlPath": "ignored.xml"},
            patch_target={"targetSql": "SELECT id FROM users WHERE"},
            patch_text="diff",
            replay_result=ReplayResult(
                matches_target=True,
                rendered_sql="SELECT id FROM users WHERE",
                normalized_rendered_sql="SELECT id FROM users WHERE",
                drift_reason=None,
            ),
            artifact=PatchArtifactResult(
                applied=True,
                xml_parse_ok=True,
                patched_text="<mapper />",
                root=None,
                reason_code=None,
            ),
        )

        self.assertFalse(result.sql_parse_ok)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason_code, "PATCH_SQL_PARSE_FAILED")

    def test_verify_patch_syntax_accepts_placeholder_sql_shape(self) -> None:
        result = verify_patch_syntax(
            sql_unit={"xmlPath": "ignored.xml"},
            patch_target={"targetSql": "SELECT id FROM users WHERE status = #{status} ORDER BY ${orderBy}"},
            patch_text="diff",
            replay_result=ReplayResult(
                matches_target=True,
                rendered_sql="SELECT id FROM users WHERE status = #{status} ORDER BY ${orderBy}",
                normalized_rendered_sql="SELECT id FROM users WHERE status = #{status} ORDER BY ${orderBy}",
                drift_reason=None,
            ),
            artifact=PatchArtifactResult(
                applied=True,
                xml_parse_ok=True,
                patched_text="<mapper />",
                root=None,
                reason_code=None,
            ),
        )

        self.assertTrue(result.sql_parse_ok)
        self.assertTrue(result.ok)
        self.assertIsNone(result.reason_code)


if __name__ == "__main__":
    unittest.main()
