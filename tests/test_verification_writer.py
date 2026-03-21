from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.verification.models import VerificationCheck, VerificationRecord
from sqlopt.verification.summary import summarize_records
from sqlopt.verification.writer import append_verification_record, write_verification_summary

ROOT = Path(__file__).resolve().parents[1]


class VerificationWriterTest(unittest.TestCase):
    def test_writer_appends_records_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_writer_") as td:
            run_dir = Path(td)
            validator = ContractValidator(ROOT)
            record = VerificationRecord(
                run_id="run_demo",
                sql_key="demo.user.listUsers#v1",
                statement_key="demo.user.listUsers",
                phase="validate",
                status="PARTIAL",
                reason_code="VALIDATE_DB_UNREACHABLE",
                reason_message="validate used a degraded DB-unreachable fallback",
                evidence_refs=[
                    "runs/run_demo/optimize/validation/acceptance.results.jsonl"
                ],
                inputs={"db_reachable": False},
                checks=[VerificationCheck("perf_checked_or_explained", True, "warn")],
                verdict={"status": "PASS"},
                created_at="2026-03-03T00:00:00+00:00",
            )

            payload = append_verification_record(run_dir, validator, record)
            summary = summarize_records("run_demo", [payload], total_sql=1)
            summary_payload = write_verification_summary(run_dir, validator, summary)
            ledger_path = run_dir / "supervisor" / "verification" / "ledger.jsonl"
            summary_path = run_dir / "supervisor" / "verification" / "summary.json"
            self.assertTrue(ledger_path.exists())
            self.assertTrue(summary_path.exists())
            ledger_rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(ledger_rows), 1)
            self.assertEqual(ledger_rows[0]["phase"], "validate")
            self.assertEqual(summary_payload["partial_count"], 1)
            self.assertEqual(summary_payload["coverage_by_phase"]["validate"]["ratio"], 1.0)
            self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["run_id"], "run_demo")

    def test_summary_counts_check_level_reason_codes(self) -> None:
        summary = summarize_records(
            "run_demo",
            [
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.listUsers#v1",
                    "statement_key": "demo.user.listUsers",
                    "phase": "optimize",
                    "status": "PARTIAL",
                    "reason_code": "RISKY_DOLLAR_SUBSTITUTION",
                    "checks": [
                        {
                            "name": "db_explain_syntax_ok",
                            "ok": False,
                            "severity": "warn",
                            "reason_code": "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR",
                        }
                    ],
                }
            ],
            total_sql=1,
        )
        top_codes = {row["reason_code"] for row in summary.to_contract()["top_reason_codes"]}
        self.assertIn("RISKY_DOLLAR_SUBSTITUTION", top_codes)
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", top_codes)
