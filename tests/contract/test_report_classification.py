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
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "optimize").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "validate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "patch_generate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "sqlunits.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.findUsers#v1"}) + "\n", encoding="utf-8"
            )
            (run_dir / "pipeline" / "optimize" / "optimization.proposals.jsonl").write_text(
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
            (run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").write_text(
                "\n".join(json.dumps(x, ensure_ascii=False) for x in acceptance_rows) + "\n",
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl").write_text("", encoding="utf-8")
            (run_dir / "pipeline" / "manifest.jsonl").write_text(
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

            self.assertEqual(report["stats"]["db_unreachable_count"], 1)
            self.assertEqual(report["stats"]["degradable_count"], 1)
            self.assertEqual(report["stats"]["retryable_count"], 1)
            self.assertEqual(report["stats"]["fatal_count"], 1)
            self.assertEqual(report["summary"]["release_readiness"], "NO_GO")
            self.assertIn("UNMATERIALIZABLE", report["stats"]["materialization_mode_counts"])
            self.assertEqual(report["stats"]["materialization_reason_counts"]["FRAGMENT_MATERIALIZATION_DISABLED"], 1)
            self.assertEqual(report["stats"]["materialization_reason_counts"]["VALIDATE_EQUIVALENCE_MISMATCH"], 1)
            self.assertEqual(report["stats"]["materialization_reason_group_counts"]["FEATURE_DISABLED"], 1)
            self.assertEqual(report["stats"]["materialization_reason_group_counts"]["OTHER"], 1)
            self.assertIn("actionability", report["stats"])
            self.assertIn("top_actionable_sql", report["stats"])
            self.assertIn("delivery_tier", report["stats"]["top_actionable_sql"][0])
            self.assertIn("semantic_gate_status", report["stats"]["top_actionable_sql"][0])
            self.assertIn("semantic_confidence_upgraded", report["stats"]["top_actionable_sql"][0])
            self.assertIn("semantic_unupgraded_reason", report["stats"]["top_actionable_sql"][0])
            self.assertIn("semantic_blocked_reason", report["stats"]["top_actionable_sql"][0])
            failures = (run_dir / "pipeline" / "ops" / "failures.jsonl").read_text(encoding="utf-8")
            self.assertIn('"classification": "degradable"', failures)
            self.assertIn('"classification": "retryable"', failures)
            self.assertIn('"classification": "fatal"', failures)
            report_md = (run_dir / "overview" / "report.md").read_text(encoding="utf-8")
            self.assertIn("## 执行决策", report_md)
            self.assertIn("## 优先处理的 SQL", report_md)
            self.assertIn("当前原因", report_md)
            self.assertIn("## 变更组合", report_md)
            self.assertIn("## 优化建议分析", report_md)
            self.assertIn("## 行动计划", report_md)
            self.assertIn("pipeline/optimize/optimization.proposals.jsonl", report_md)
            self.assertIn("pipeline/validate/acceptance.results.jsonl", report_md)
            self.assertIn("pipeline/patch_generate/patch.results.jsonl", report_md)
            self.assertIn("物化", report_md)
            self.assertIn("## 验证警告", report_md)
            self.assertIn("语义门", report_md)
            self.assertIn("升级轨迹", report_md)
            self.assertIn("未升级主因", report_md)
            self.assertIn("阻断主因", report_md)
            summary_md = (run_dir / "overview" / "report.summary.md").read_text(encoding="utf-8")
            self.assertIn("## 优先处理的 SQL", summary_md)
            self.assertTrue(
                ("当前置信度低于领先候选" in summary_md) or ("语义证据强度不足" in summary_md),
                summary_md,
            )
            self.assertIn("置信度升级", summary_md)
            self.assertTrue((run_dir / "run.index.json").exists())
            run_index = json.loads((run_dir / "run.index.json").read_text(encoding="utf-8"))
            self.assertIn("integrity", run_index)
            self.assertIn("status", run_index["integrity"])
            self.assertEqual(run_index["groups"]["sql"]["catalog"], "sql/catalog.jsonl")
            self.assertIn("pipeline/scan/sqlunits.jsonl", run_index["groups"]["pipeline"])
            self.assertIn("pipeline/optimize/optimization.proposals.jsonl", run_index["groups"]["pipeline"])
            self.assertIn("pipeline/validate/acceptance.results.jsonl", run_index["groups"]["pipeline"])
            self.assertIn("pipeline/patch_generate/patch.results.jsonl", run_index["groups"]["pipeline"])
            self.assertTrue((run_dir / "overview" / "report.json").exists())
            self.assertTrue((run_dir / "pipeline" / "manifest.jsonl").exists())
            self.assertTrue((run_dir / "pipeline" / "scan" / "sqlunits.jsonl").exists())
            self.assertTrue((run_dir / "pipeline" / "optimize" / "optimization.proposals.jsonl").exists())
            self.assertTrue((run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").exists())
            self.assertTrue((run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl").exists())
            self.assertTrue((run_dir / "sql" / "catalog.jsonl").exists())
            self.assertTrue((run_dir / "diagnostics" / "sql_outcomes.jsonl").exists())
            self.assertTrue((run_dir / "diagnostics" / "sql_artifacts.jsonl").exists())
            self.assertTrue((run_dir / "diagnostics" / "blockers.summary.json").exists())

    def test_report_generate_tolerates_missing_stage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_") as td:
            run_dir = Path(td)
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor" / "state.json").write_text(
                json.dumps({"phase_status": {"preflight": "DONE", "scan": "FAILED", "optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING", "report": "PENDING"}}),
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "manifest.jsonl").write_text(
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
            self.assertEqual(report["stats"]["sql_units"], 0)
            self.assertGreaterEqual(report["stats"]["fatal_count"], 1)
            self.assertTrue((run_dir / "overview" / "report.md").exists())
            self.assertTrue((run_dir / "overview" / "report.summary.md").exists())

    def test_report_warns_and_optionally_blocks_on_unverified_critical_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_gate_") as td:
            run_dir = Path(td)
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "optimize").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "validate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "patch_generate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "sqlunits.jsonl").write_text(json.dumps({"sqlKey": "demo.user.findUsers#v1"}) + "\n", encoding="utf-8")
            (run_dir / "pipeline" / "optimize" / "optimization.proposals.jsonl").write_text("", encoding="utf-8")
            (run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.findUsers#v1",
                        "status": "PASS",
                        "equivalence": {"checked": True},
                        "perfComparison": {"checked": True, "reasonCodes": []},
                        "securityChecks": {"dollar_substitution_removed": True},
                        "selectedCandidateSource": "heuristic",
                        "selectedCandidateId": "c1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl").write_text("", encoding="utf-8")
            (run_dir / "pipeline" / "verification" / "ledger.jsonl").write_text(
                json.dumps(
                    {
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
                    }
                )
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
                "verification": {"enforce_verified_outputs": False, "critical_output_policy": "warn"},
            }
            validator = ContractValidator(ROOT)

            report = report_stage.generate("rpt_gate", "analyze", config, run_dir, validator)

            self.assertEqual(report["evidence_confidence"], "LOW")
            self.assertIn("UNVERIFIED_PASS_ACCEPTANCE", report["validation_warnings"][0])
            summary_md = (run_dir / "overview" / "report.summary.md").read_text(encoding="utf-8")
            self.assertIn("## 警告", summary_md)
            self.assertIn("UNVERIFIED_PASS_ACCEPTANCE", summary_md)

            config["verification"]["enforce_verified_outputs"] = False
            config["verification"]["critical_output_policy"] = "block"
            with self.assertRaises(StageError):
                report_stage.generate("rpt_gate", "analyze", config, run_dir, validator)
            self.assertTrue((run_dir / "overview" / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
