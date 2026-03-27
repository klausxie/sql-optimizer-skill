from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.verification.patch_artifact import materialize_patch_artifact


class PatchArtifactTest(unittest.TestCase):
    def test_materialize_patch_artifact_rejects_hunk_start_beyond_source_length(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_artifact_") as td:
            xml_path = Path(td) / "demo.xml"
            xml_path.write_text("<mapper/>\n", encoding="utf-8")
            patch_text = (
                f"--- a/{xml_path.as_posix()}\n"
                f"+++ b/{xml_path.as_posix()}\n"
                "@@ -5,0 +5,1 @@\n"
                "+<extra/>\n"
            )

            result = materialize_patch_artifact(
                sql_unit={"xmlPath": str(xml_path)},
                patch_text=patch_text,
            )

        self.assertFalse(result.applied)
        self.assertEqual(result.reason_code, "PATCH_ARTIFACT_INVALID")


if __name__ == "__main__":
    unittest.main()
