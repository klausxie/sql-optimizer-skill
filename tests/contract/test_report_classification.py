from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.errors import StageError
from sqlopt.stages import report as report_stage

ROOT = Path(__file__).resolve().parents[1]


class ReportClassificationTest(unittest.TestCase):
    def test_report_classifies_failures_and_db_unreachable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "scan.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1"}) + "\n", encoding="utf-8"
            )
            (run_dir / "artifacts" / "proposals.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1", "issues": [], "dbEvidenceSummary": {}, "planSummary": {}, "suggestions": [], "verdict": "NOOP"})
                + "\n",
                encoding="utf-8",
            )
            acceptance_rows = [
                {
                    "sqlKey": "demo.user.findUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "equivalence": {"checked": False},
                    "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "securityChecks": {"dollar_substitution_removed": True},
                    "rewriteMaterialization": {"mode": "UNMATERIALIZABLE", "reasonCode": "FRAGMENT_MATERIALIZATION_DISABLED"},
                    "semanticEquivalence": {
                        "status": "PASS",
                        "confidence": "LOW",
                        "confidenceBeforeUpgrade": "LOW",
                        "confidenceUpgradeApplied": False,
                        "confidenceUpgradeReasons": [],
                        "confidenceUpgradeEvidenceSources": [],
                    },
                    "feedback": {"reason_code": "VALIDATE_DB_UNREACHABLE"},
                },
                {
                    "sqlKey": "demo.user.findUsers#v2",
                    "status": "FAIL",
                    "equivalence": {"checked": True},
                    "perfComparison": {"checked": False},
                    "securityChecks": {"dollar_substitution_removed": False},
                    "rewriteMaterialization": {"mode": "UNMATERIALIZABLE", "reasonCode": "VALIDATE_EQUIVALENCE_MISMATCH"},
                    "semanticEquivalence": {
                        "status": "FAIL",
                        "confidence": "HIGH",
                        "confidenceBeforeUpgrade": "MEDIUM",
                        "confidenceUpgradeApplied": True,
                        "confidenceUpgradeReasons": ["SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_EXACT"],
                        "confidenceUpgradeEvidenceSources": ["DB_FINGERPRINT"],
                    },
                    "feedback": {"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH"},
                },
            ]
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in acceptance_rows) + "\n",
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "patches.jsonl").write_text("", encoding="utf-8")
            (run_dir / "control" / "manifest.jsonl").write_text(
                json.dumps({"event": "failed", "payload": {"reason_code": "RUNTIME_STAGE_TIMEOUT", "statement_key": "demo.user.findUsers#v2"}})
                + "\n",
                encoding="utf-8",
            )
            config = {
                "policy": {
                    "require_perf_improvement": False,
                    "cost_threshold_pct": 0,
                    "allow_seq_scan_if_rows_below": 0,
                    "semantic_strict_mode": True,
                },
                "runtime": {
                    "stage_timeout_ms": {"scan": 1, "optimize": 1, "validate": 1, "apply": 1, "report": 1},
                    "stage_retry_max": {"scan": 0, "optimize": 0, "validate": 0, "apply": 0, "report": 0},
                    "stage_retry_backoff_ms": 1,
                },
                "llm": {"enabled": False},
                "validate": {"db_unreachable_high_rate_threshold": 0.5},
            }
            validator = ContractValidator(ROOT)
            report = report_stage.generate("rpt_1", "analyze", config, run_dir, validator)

            self.assertEqual(
                set(report.keys()),
                {
                    "run_id",
                    "generated_at",
                    "target_stage",
                    "status",
                    "verdict",
                    "next_action",
                    "phase_status",
                    "stats",
                    "blockers",
                },
            )
            self.assertEqual(report["run_id"], "rpt_1")
            self.assertEqual(report["target_stage"], "report")
            self.assertEqual(report["status"], "DONE")
            self.assertEqual(report["verdict"], "BLOCKED")
            self.assertEqual(report["next_action"], "inspect")
            self.assertEqual(report["stats"]["sql_total"], 1)
            self.assertEqual(report["stats"]["proposal_total"], 1)
            self.assertEqual(report["stats"]["accepted_total"], 0)
            self.assertEqual(report["stats"]["patchable_total"], 0)
            self.assertEqual(report["stats"]["patched_total"], 0)
            self.assertEqual(report["stats"]["blocked_total"], 2)
            top_codes = {row["code"]: row["count"] for row in report["blockers"]["top_reason_codes"]}
            self.assertEqual(top_codes["VALIDATE_DB_UNREACHABLE"], 1)
            self.assertEqual(top_codes["VALIDATE_EQUIVALENCE_MISMATCH"], 1)
            self.assertTrue((run_dir / "report.json").exists())
            self.assertTrue((run_dir / "control" / "manifest.jsonl").exists())
            self.assertTrue((run_dir / "artifacts" / "scan.jsonl").exists())
            self.assertTrue((run_dir / "artifacts" / "proposals.jsonl").exists())
            self.assertTrue((run_dir / "artifacts" / "acceptance.jsonl").exists())
            self.assertTrue((run_dir / "artifacts" / "patches.jsonl").exists())
            self.assertTrue((run_dir / "sql" / "catalog.jsonl").exists())

    def test_report_generate_tolerates_missing_stage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_") as td:
            run_dir = Path(td)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "state.json").write_text(
                json.dumps({"phase_status": {"preflight": "DONE", "scan": "FAILED", "optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING", "report": "PENDING"}}),
                encoding="utf-8",
            )
            (run_dir / "control" / "manifest.jsonl").write_text(
                json.dumps({"stage": "scan", "event": "failed", "payload": {"reason_code": "SCAN_MAPPER_NOT_FOUND"}}) + "\n",
                encoding="utf-8",
            )
            config = {
                "policy": {
                    "require_perf_improvement": False,
                    "cost_threshold_pct": 0,
                    "allow_seq_scan_if_rows_below": 0,
                    "semantic_strict_mode": True,
                },
                "runtime": {
                    "stage_timeout_ms": {"scan": 1, "optimize": 1, "validate": 1, "apply": 1, "report": 1},
                    "stage_retry_max": {"scan": 0, "optimize": 0, "validate": 0, "apply": 0, "report": 0},
                    "stage_retry_backoff_ms": 1,
                },
                "llm": {"enabled": False},
            }
            validator = ContractValidator(ROOT)
            report = report_stage.generate("rpt_missing", "analyze", config, run_dir, validator)
            self.assertEqual(report["stats"]["sql_total"], 0)
            self.assertEqual(report["next_action"], "inspect")
            self.assertGreaterEqual(report["blockers"]["top_reason_codes"][0]["count"], 1)
            self.assertTrue((run_dir / "report.json").exists())

    def test_report_warns_and_optionally_blocks_on_unverified_critical_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_gate_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "scan.jsonl").write_text(json.dumps({"sqlKey": "demo.user.findUsers#v1"}) + "\n", encoding="utf-8")
            (run_dir / "artifacts" / "proposals.jsonl").write_text("", encoding="utf-8")
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "status": "PASS",
                        "equivalence": {"checked": True},
                        "perfComparison": {"checked": True, "reasonCodes": []},
                        "securityChecks": {"dollar_substitution_removed": True},
                        "selectedCandidateSource": "heuristic",
                        "selectedCandidateId": "c1",
                        "verification": {
                            "run_id": "rpt_gate",
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
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "patches.jsonl").write_text("", encoding="utf-8")
            config = {
                "policy": {
                    "require_perf_improvement": False,
                    "cost_threshold_pct": 0,
                    "allow_seq_scan_if_rows_below": 0,
                    "semantic_strict_mode": True,
                },
                "runtime": {
                    "stage_timeout_ms": {"scan": 1, "optimize": 1, "validate": 1, "apply": 1, "report": 1},
                    "stage_retry_max": {"scan": 0, "optimize": 0, "validate": 0, "apply": 0, "report": 0},
                    "stage_retry_backoff_ms": 1,
                },
                "llm": {"enabled": False},
                "verification": {"enforce_verified_outputs": False, "critical_output_policy": "warn"},
            }
            validator = ContractValidator(ROOT)

            report = report_stage.generate("rpt_gate", "analyze", config, run_dir, validator)

            self.assertEqual(report["next_action"], "inspect")
            top_codes = {row["code"] for row in report["blockers"]["top_reason_codes"]}
            self.assertIn("UNVERIFIED_PASS_ACCEPTANCE", top_codes)
            self.assertTrue((run_dir / "report.json").exists())

            config["verification"]["enforce_verified_outputs"] = False
            config["verification"]["critical_output_policy"] = "block"
            with self.assertRaises(StageError):
                report_stage.generate("rpt_gate", "analyze", config, run_dir, validator)
            self.assertTrue((run_dir / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
