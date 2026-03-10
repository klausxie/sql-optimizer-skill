from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.stages.patch_generate import execute_one

ROOT = Path(__file__).resolve().parents[1]


class PatchConflictTest(unittest.TestCase):
    def test_multi_variant_pass_conflict_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_") as td:
            run_dir = Path(td)
            (run_dir / "pipeline" / "validate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "patch_generate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "manifest.jsonl").write_text("", encoding="utf-8")
            rows = [
                {"sqlKey": "demo.user.findUsers#v1", "status": "PASS", "equivalence": {}, "perfComparison": {}, "securityChecks": {}},
                {"sqlKey": "demo.user.findUsers#v2", "status": "PASS", "equivalence": {}, "perfComparison": {}, "securityChecks": {}},
            ]
            (run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8"
            )
            unit = {"sqlKey": "demo.user.findUsers#v1", "locators": {"statementId": "findUsers"}}
            validator = ContractValidator(ROOT)
            patch = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=rows[0], validator=validator)

        self.assertTrue(patch["diffSummary"]["skipped"])
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_CONFLICT_NO_CLEAR_WINNER")
        self.assertEqual(patch.get("statementKey"), "demo.user.findUsers")


if __name__ == "__main__":
    unittest.main()
