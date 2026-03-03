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
        self.assertFalse(args.summary_only)
        self.assertEqual(args.format, "json")

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
        self.assertEqual(payload["delivery_assessment"], "READY_TO_APPLY")
        self.assertEqual(payload["evidence_state"], "CRITICAL_GAP")
        self.assertEqual(payload["recommended_next_step"]["action"], "review-evidence")
        self.assertEqual(payload["decision_summary"], "critical verification evidence is incomplete for this output")
        self.assertIn("missing verification evidence", payload["why_now"])
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
        self.assertEqual(payload["delivery_assessment"], "BLOCKED")

    def test_cmd_verify_summary_only_returns_compact_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_summary_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text(
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
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1", "status": "PASS"}) + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "NEEDS_REVIEW")
        self.assertEqual(payload["evidence_state"], "CRITICAL_GAP")
        self.assertIn("decision_summary", payload)
        self.assertIn("why_now", payload)
        self.assertNotIn("records", payload)
        self.assertEqual(payload["recommended_next_step"]["action"], "review-evidence")
        self.assertEqual(payload["repair_hints"], [])

    def test_cmd_verify_summary_only_prefers_template_rewrite_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_template_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text("", encoding="utf-8")
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "status": "PASS",
                        "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "patches" / "patch.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "deliveryOutcome": {
                            "tier": "PATCHABLE_WITH_REWRITE",
                            "summary": "patch can likely land after template-aware mapper refactoring",
                        },
                        "repairHints": [{"hintId": "expand-include", "title": "Refactor include fragment path"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "PATCHABLE_WITH_REWRITE")
        self.assertEqual(payload["evidence_state"], "COMPLETE")
        self.assertEqual(payload["recommended_next_step"]["action"], "refactor-mapper")
        self.assertIn("template-aware refactoring", payload["decision_summary"])
        self.assertIn("mapper is refactored for template safety", payload["why_now"])
        self.assertEqual(payload["repair_hints"][0]["hintId"], "expand-include")

    def test_cmd_verify_summary_only_uses_decision_layers_when_legacy_fields_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_decision_layers_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text("", encoding="utf-8")
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "decisionLayers": {
                            "evidence": {"degraded": False, "reasonCodes": []},
                            "delivery": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                            "acceptance": {"status": "PASS"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "PATCHABLE_WITH_REWRITE")
        self.assertEqual(payload["evidence_state"], "COMPLETE")
        self.assertEqual(payload["recommended_next_step"]["action"], "refactor-mapper")

    def test_cmd_verify_summary_only_prefers_manual_review_guidance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_manual_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text("", encoding="utf-8")
            (run_dir / "patches" / "patch.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "deliveryOutcome": {
                            "tier": "MANUAL_REVIEW",
                            "summary": "rewrite is plausible, but the generated patch needs manual conflict resolution",
                        },
                        "repairHints": [
                            {
                                "hintId": "review-target-drift",
                                "title": "Check target mapper drift",
                                "command": "git diff -- mapper.xml",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "MANUAL_REVIEW")
        self.assertEqual(payload["evidence_state"], "COMPLETE")
        self.assertEqual(payload["recommended_next_step"]["action"], "resolve-patch-conflict")
        self.assertEqual(payload["recommended_next_step"]["command"], "git diff -- mapper.xml")

    def test_cmd_verify_summary_only_prefers_db_recheck_when_decision_layers_degraded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_db_recheck_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text("", encoding="utf-8")
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "decisionLayers": {
                            "evidence": {"degraded": True, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                            "delivery": {"tier": "READY"},
                            "acceptance": {"status": "NEED_MORE_PARAMS", "feedbackReasonCode": "VALIDATE_PARAM_INSUFFICIENT"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "NEEDS_REVIEW")
        self.assertEqual(payload["evidence_state"], "DEGRADED")
        self.assertEqual(payload["recommended_next_step"]["action"], "restore-db-validation")
        self.assertIn("DB-backed validation needs to be restored", payload["why_now"])

    def test_cmd_verify_summary_only_explains_ready_to_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_ready_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text("", encoding="utf-8")
            (run_dir / "patches" / "patch.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "applicable": True,
                        "deliveryOutcome": {"tier": "READY_TO_APPLY"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=True,
                            format="json",
                        )
                    )

        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["delivery_assessment"], "READY_TO_APPLY")
        self.assertEqual(payload["evidence_state"], "COMPLETE")
        self.assertIn("fastest safe win", payload["why_now"])

    def test_cmd_verify_text_format_prints_summary_lines(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_verify_text_") as td:
            run_dir = Path(td)
            (run_dir / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "verification" / "ledger.jsonl").write_text(
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
                        "created_at": "2026-03-03T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "patches" / "patch.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "deliveryOutcome": {"tier": "MANUAL_REVIEW"},
                        "repairHints": [{"hintId": "review-target-drift", "title": "Check target mapper drift"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            buf = io.StringIO()
            with patch("sqlopt.cli._resolve_run_dir", return_value=run_dir):
                with redirect_stdout(buf):
                    cmd_verify(
                        SimpleNamespace(
                            run_id="run_demo",
                            sql_key="demo.user.findUsers#v1",
                            phase=None,
                            summary_only=False,
                            format="text",
                        )
                    )

        text = buf.getvalue()
        self.assertIn("SQL: demo.user.findUsers#v1", text)
        self.assertIn("Decision:", text)
        self.assertIn("Delivery:", text)
        self.assertIn("Top Hint: Check target mapper drift", text)
        self.assertIn("Next Step:", text)


if __name__ == "__main__":
    unittest.main()
