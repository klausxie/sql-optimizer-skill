from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.stages.patch_verification import append_patch_verification

ROOT = Path(__file__).resolve().parents[1]


def _read_ledger(run_dir: Path) -> list[dict]:
    ledger = run_dir / "pipeline" / "verification" / "ledger.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]


class PatchVerificationTest(unittest.TestCase):
    def _validator(self) -> ContractValidator:
        return ContractValidator(ROOT)

    def test_applicable_patch_is_recorded_as_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_ok_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
            }
            acceptance = {"status": "PASS"}
            append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["phase"], "patch_generate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SELECTED_SINGLE_PASS")

    def test_template_ops_without_replay_are_recorded_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_unverified_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE", "message": "needs rewrite"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "templateRewriteOps": [{"op": "replace_statement_body"}],
                "rewriteMaterialization": {"replayVerified": False},
            }
            append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED")

    def test_semantic_gate_block_is_recorded_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_semantic_gate_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS", "message": "blocked by semantic gate"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "semanticEquivalence": {"status": "UNCERTAIN"},
            }
            append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="UNCERTAIN",
                semantic_gate_confidence="LOW",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS")

    def test_semantic_low_confidence_block_is_recorded_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_semantic_confidence_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_SEMANTIC_CONFIDENCE_LOW", "message": "blocked by low confidence"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "semanticEquivalence": {"status": "PASS", "confidence": "LOW"},
            }
            append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="LOW",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SEMANTIC_CONFIDENCE_LOW")


if __name__ == "__main__":
    unittest.main()
