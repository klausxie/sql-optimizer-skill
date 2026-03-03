from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ManifestEvent, ReportInputs, ReportStateSnapshot


class ReportBuilderTest(unittest.TestCase):
    def test_build_report_artifacts_aggregates_failures_and_phase_coverage(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [{"code": "SELECT_STAR"}],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 85,
                        "tier": "HIGH",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT"},
                    "perfComparison": {"reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "statementKey": "demo.user.listUsers",
                    "applicable": True,
                    "deliveryOutcome": {"tier": "READY_TO_APPLY", "summary": "patch is ready to apply"},
                }
            ],
            state=ReportStateSnapshot(
                phase_status={"preflight": "DONE", "scan": "DONE", "report": "DONE"},
                attempts_by_phase={"report": 1},
            ),
            manifest_rows=[
                ManifestEvent(
                    stage="preflight",
                    event="failed",
                    payload={"reason_code": "PREFLIGHT_SCANNER_MISSING"},
                )
            ],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.listUsers#v1",
                    "statement_key": "demo.user.listUsers",
                    "phase": "validate",
                    "status": "PARTIAL",
                    "reason_code": "VALIDATE_DB_UNREACHABLE",
                    "reason_message": "degraded DB fallback",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["sql_units"], 1)
        self.assertEqual(artifacts.report.stats["acceptance_need_more_params"], 1)
        self.assertEqual(artifacts.report.stats["preflight_failure_count"], 1)
        self.assertEqual(artifacts.report.stats["pipeline_coverage"]["report"], "DONE")
        self.assertEqual(len(artifacts.failures), 2)
        self.assertEqual(artifacts.failures[0].phase, "validate")
        self.assertIn("validate", artifacts.report.stats["phase_reason_code_counts"])
        self.assertIn("preflight", artifacts.report.stats["phase_reason_code_counts"])
        self.assertEqual(artifacts.report.stats["verification"]["partial_count"], 1)
        self.assertNotIn("generated_at", artifacts.report.stats["verification"])
        self.assertIn("actionability", artifacts.report.stats)
        self.assertIn("top_actionable_sql", artifacts.report.stats)
        self.assertEqual(len(artifacts.report.stats["top_actionable_sql"]), 1)
        self.assertIn("priority", artifacts.report.stats["top_actionable_sql"][0])
        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["delivery_tier"], "READY_TO_APPLY")
        self.assertIn("summary", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("why_now", artifacts.report.stats["top_actionable_sql"][0])
        self.assertEqual(artifacts.report.evidence_confidence, "MEDIUM")
        self.assertIsNone(artifacts.report.validation_warnings)
        self.assertEqual(artifacts.verification_summary["coverage_by_phase"]["validate"]["ratio"], 1.0)
        self.assertEqual(artifacts.topology.runtime_policy["stage_timeout_ms"]["report"], 300)
        self.assertEqual(artifacts.health.report_json, str(Path(td) / "report.json"))

    def test_build_report_artifacts_warns_on_optimize_db_explain_syntax_error(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findUsers#v1"}],
            proposals=[],
            acceptance=[],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.findUsers#v1",
                    "statement_key": "demo.user.findUsers",
                    "phase": "optimize",
                    "status": "PARTIAL",
                    "reason_code": "RISKY_DOLLAR_SUBSTITUTION",
                    "reason_message": "skip LLM for unsafe dollar substitution",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [
                        {
                            "name": "db_explain_syntax_ok",
                            "ok": False,
                            "severity": "warn",
                            "reason_code": "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR",
                            "detail": "You have an error in your SQL syntax near ILIKE",
                            "evidence_ref": None,
                        }
                    ],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_opt_warn_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertIsNotNone(artifacts.report.validation_warnings)
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", artifacts.report.validation_warnings[0])
        top_reason_codes = {row["reason_code"] for row in artifacts.report.stats["verification"]["top_reason_codes"]}
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", top_reason_codes)

    def test_action_plan_prefers_delivery_specific_guidance(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findIncluded#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "issues": [{"code": "SELECT_STAR"}],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 75,
                        "tier": "MEDIUM",
                        "autoPatchLikelihood": "MEDIUM",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "status": "PASS",
                    "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                    "perfComparison": {"reasonCodes": []},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "statementKey": "demo.user.findIncluded",
                    "applicable": None,
                    "deliveryOutcome": {
                        "tier": "PATCHABLE_WITH_REWRITE",
                        "summary": "patch can likely land after template-aware mapper refactoring",
                    },
                    "repairHints": [
                        {
                            "hintId": "expand-include",
                            "title": "Refactor include fragment path",
                            "command": None,
                        }
                    ],
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_actions_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.next_actions[0]["action_id"], "refactor-mapper")
        self.assertIn("template-aware refactoring", artifacts.next_actions[0]["reason"])

    def test_action_plan_prefers_decision_layers_degraded_db_recheck(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 70,
                        "tier": "MEDIUM",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "perfComparison": {"reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "decisionLayers": {
                        "evidence": {"degraded": True, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "NEED_MORE_PARAMS", "feedbackReasonCode": "VALIDATE_PARAM_INSUFFICIENT"},
                    },
                }
            ],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_decision_layers_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_degraded"], True)
        self.assertEqual(artifacts.next_actions[0]["action_id"], "check-db")

    def test_action_plan_prefers_evidence_review_for_critical_gap(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 85,
                        "tier": "HIGH",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "PASS",
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": []},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "PASS"},
                    },
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "statementKey": "demo.user.listUsers",
                    "applicable": True,
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.listUsers#v1",
                    "statement_key": "demo.user.listUsers",
                    "phase": "validate",
                    "status": "UNVERIFIED",
                    "reason_code": "VALIDATE_PASS_SELECTION_INCOMPLETE",
                    "reason_message": "missing evidence",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_critical_gap_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_state"], "CRITICAL_GAP")
        self.assertIn("critical verification evidence", artifacts.report.stats["top_actionable_sql"][0]["summary"])
        self.assertIn("critical evidence is missing", artifacts.report.stats["top_actionable_sql"][0]["why_now"])
        self.assertEqual(artifacts.next_actions[0]["action_id"], "review-evidence")


if __name__ == "__main__":
    unittest.main()
