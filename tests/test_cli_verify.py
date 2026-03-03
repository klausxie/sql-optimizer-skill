from __future__ import annotations

import ast
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlopt.cli import build_parser, cmd_verify


class CliVerifyTest(unittest.TestCase):
    def test_build_parser_registers_verify_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "--run-id", "run_demo", "--sql-key", "demo.user.findUsers#v1"])
        self.assertEqual(args.cmd, "verify")
        self.assertEqual(args.run_id, "run_demo")
        self.assertEqual(args.sql_key, "demo.user.findUsers#v1")
        self.assertIsNone(args.phase)

    def test_cmd_verify_returns_filtered_records_and_related_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "run_id": "run_demo",
                                "sql_key": "demo.user.findUsers#v1",
                                "statement_key": "demo.user.findUsers",
                                "phase": "validate",
                                "status": "UNVERIFIED",
                                "reason_code": "VALIDATE_PASS_SELECTION_INCOMPLETE",
                                "reason_message": "missing selection evidence",
                                "evidence_refs": [],
                                "inputs": {},
                                "checks": [],
                                "verdict": {},
                                "created_at": "2026-03-03T00:00:00+00:00",
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "run_demo",
                                "sql_key": "demo.user.findUsers#v1",
                                "statement_key": "demo.user.findUsers",
                                "phase": "patch_generate",
                                "status": "VERIFIED",
                                "reason_code": "PATCH_READY",
                                "reason_message": "patch branch selected",
                                "evidence_refs": [],
                                "inputs": {},
                                "checks": [],
                                "verdict": {},
                                "created_at": "2026-03-03T00:00:01+00:00",
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "run_demo",
                                "sql_key": "demo.user.findUsers#v2",
                                "statement_key": "demo.user.findUsers",
                                "phase": "validate",
                                "status": "VERIFIED",
                                "reason_code": "VALIDATE_PASS",
                                "reason_message": "evidence complete",
                                "evidence_refs": [],
                                "inputs": {},
                                "checks": [],
                                "verdict": {},
                                "created_at": "2026-03-03T00:00:02+00:00",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1", "status": "PASS"}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "patches" / "patch.results.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1", "applicable": True}) + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(SimpleNamespace(run_id="run_demo", sql_key="demo.user.findUsers#v1", phase=None))

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertTrue(payload["verification_available"])
        self.assertEqual(payload["record_count"], 2)
        self.assertEqual(payload["status_counts"]["UNVERIFIED"], 1)
        self.assertEqual(payload["status_counts"]["VERIFIED"], 1)
        self.assertTrue(payload["has_unverified"])
        self.assertTrue(payload["acceptance"])
        self.assertTrue(payload["patches"])
        self.assertEqual(len(payload["records"]), 2)

    def test_cmd_verify_applies_phase_filter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_phase_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "run_id": "run_demo",
                                "sql_key": "demo.user.findUsers#v1",
                                "statement_key": "demo.user.findUsers",
                                "phase": "scan",
                                "status": "VERIFIED",
                                "reason_code": "SCAN_OK",
                                "reason_message": "scan complete",
                                "evidence_refs": [],
                                "inputs": {},
                                "checks": [],
                                "verdict": {},
                                "created_at": "2026-03-03T00:00:00+00:00",
                            }
                        ),
                        json.dumps(
                            {
                                "run_id": "run_demo",
                                "sql_key": "demo.user.findUsers#v1",
                                "statement_key": "demo.user.findUsers",
                                "phase": "validate",
                                "status": "PARTIAL",
                                "reason_code": "VALIDATE_DB_UNREACHABLE",
                                "reason_message": "fallback used",
                                "evidence_refs": [],
                                "inputs": {},
                                "checks": [],
                                "verdict": {},
                                "created_at": "2026-03-03T00:00:01+00:00",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(SimpleNamespace(run_id="run_demo", sql_key="demo.user.findUsers#v1", phase="validate"))

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["record_count"], 1)
        self.assertEqual(payload["phase"], "validate")
        self.assertEqual(payload["status_counts"]["PARTIAL"], 1)
        self.assertFalse(payload["has_unverified"])
        self.assertTrue(payload["has_partial"])


if __name__ == "__main__":
    unittest.main()
