from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ManifestEvent, ReportInputs, ReportStateSnapshot


def _config() -> dict:
    return {
        "policy": {},
        "runtime": {
            "stage_timeout_ms": {"report": 300},
            "stage_retry_max": {"report": 2},
            "stage_retry_backoff_ms": 50,
        },
        "llm": {"enabled": False},
    }


class ReportBuilderTest(unittest.TestCase):
    def test_build_report_artifacts_keeps_summary_minimal_and_generates_catalog(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers", "statementKey": "demo.user.listUsers"}],
            proposals=[{"sqlKey": "demo.user.listUsers", "statementKey": "demo.user.listUsers", "verdict": "CAN_IMPROVE", "issues": []}],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers",
                    "statementKey": "demo.user.listUsers",
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT"},
                    "equivalence": {"checked": False},
                    "semanticEquivalence": {"status": "UNCERTAIN", "confidence": "UNKNOWN"},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.listUsers",
                    "statementKey": "demo.user.listUsers",
                    "applicable": True,
                    "deliveryOutcome": {"tier": "READY_TO_APPLY", "summary": "patch is ready"},
                }
            ],
            state=ReportStateSnapshot(
                phase_status={"preflight": "DONE", "scan": "DONE", "report": "DONE"},
                attempts_by_phase={"report": 1},
                selection_scope={"selected_count": 1},
            ),
            manifest_rows=[
                ManifestEvent(stage="preflight", event="failed", payload={"reason_code": "PREFLIGHT_SCANNER_MISSING"})
            ],
            verification_rows=[],
        )

        with tempfile.TemporaryDirectory(prefix="report_builder_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", _config(), Path(td), inputs)

        self.assertEqual(
            set(artifacts.report.stats.keys()),
            {
                "sql_units",
                "proposals",
                "acceptance_pass",
                "acceptance_fail",
                "acceptance_need_more_params",
                "patch_files",
                "patch_applicable_count",
                "blocked_sql_count",
                "blocker_family_counts",
                "pipeline_coverage",
                "fatal_count",
            },
        )
        self.assertEqual(artifacts.report.stats["sql_units"], 1)
        self.assertEqual(artifacts.report.stats["acceptance_need_more_params"], 1)
        self.assertEqual(artifacts.report.stats["patch_applicable_count"], 1)
        self.assertEqual(artifacts.report.stats["blocker_family_counts"], {"READY": 1})
        self.assertEqual(artifacts.report.next_action, "inspect")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "inspect")
        self.assertEqual(artifacts.top_blockers[0]["code"], "PREFLIGHT_SCANNER_MISSING")
        self.assertEqual(artifacts.sql_rows[0]["semantic_gate_status"], "UNCERTAIN")
        self.assertEqual(len(artifacts.diagnostics_sql_artifacts), 1)
        sql_artifact = artifacts.diagnostics_sql_artifacts[0]
        self.assertEqual(sql_artifact["artifact_refs"]["report"], "report.json")
        self.assertEqual(sql_artifact["artifact_refs"]["proposals"], "artifacts/proposals.jsonl")
        self.assertEqual(sql_artifact["artifact_refs"]["acceptance"], "artifacts/acceptance.jsonl")
        self.assertEqual(sql_artifact["artifact_refs"]["patches"], "artifacts/patches.jsonl")
        self.assertEqual(sql_artifact["delivery_status"], "READY_TO_APPLY")

    def test_build_report_artifacts_prefers_apply_when_everything_is_ready(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.countUsers", "statementKey": "demo.user.countUsers"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.countUsers",
                    "statementKey": "demo.user.countUsers",
                    "status": "PASS",
                    "equivalence": {"checked": True, "evidenceRefs": ["evidence/db.json"]},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.countUsers",
                    "statementKey": "demo.user.countUsers",
                    "applicable": True,
                    "patchFiles": ["patches/demo.patch"],
                    "strategyType": "SAFE_WRAPPER_COLLAPSE",
                    "deliveryOutcome": {"tier": "READY_TO_APPLY"},
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )

        with tempfile.TemporaryDirectory(prefix="report_builder_apply_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", _config(), Path(td), inputs)

        self.assertEqual(artifacts.report.verdict, "PASS")
        self.assertEqual(artifacts.report.next_action, "apply")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "apply")
        self.assertEqual(artifacts.report.stats["blocked_sql_count"], 0)

    def test_build_report_artifacts_surfaces_verification_gate_warnings(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findUsers", "statementKey": "demo.user.findUsers"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.findUsers",
                    "statementKey": "demo.user.findUsers",
                    "status": "PASS",
                    "equivalence": {"checked": True},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                }
            ],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.findUsers",
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
            ],
        )

        with tempfile.TemporaryDirectory(prefix="report_builder_gate_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", _config(), Path(td), inputs)

        self.assertIsNotNone(artifacts.validation_warnings)
        self.assertEqual(artifacts.report.next_action, "inspect")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "review-evidence")
        self.assertEqual(artifacts.verification_summary["coverage_by_phase"]["validate"]["ratio"], 1.0)

    def test_build_report_artifacts_preserves_dynamic_and_aggregation_catalog_fields(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.dynamic", "statementKey": "demo.user.dynamic"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.dynamic",
                    "statementKey": "demo.user.dynamic",
                    "status": "PASS",
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                    "rewriteFacts": {
                        "dynamicTemplate": {
                            "capabilityProfile": {
                                "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                                "capabilityTier": "SAFE_BASELINE",
                                "patchSurface": "STATEMENT_BODY",
                                "baselineFamily": "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
                            }
                        },
                        "aggregationQuery": {
                            "capabilityProfile": {
                                "shapeFamily": "GROUP_BY",
                                "capabilityTier": "REVIEW_REQUIRED",
                                "constraintFamily": "GROUP_BY_AGGREGATION",
                                "safeBaselineFamily": None,
                            }
                        },
                    },
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.dynamic",
                    "statementKey": "demo.user.dynamic",
                    "applicable": False,
                    "strategyType": "DYNAMIC_STATEMENT_TEMPLATE_EDIT",
                    "dynamicTemplateBlockingReason": "DYNAMIC_SAFE_BASELINE_NO_EFFECTIVE_DIFF",
                    "deliveryOutcome": {"tier": "BLOCKED"},
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )

        with tempfile.TemporaryDirectory(prefix="report_builder_catalog_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", _config(), Path(td), inputs)

        row = artifacts.diagnostics_sql_artifacts[0]
        self.assertEqual(row["aggregation_shape_family"], "GROUP_BY")
        self.assertEqual(row["aggregation_constraint_family"], "GROUP_BY_AGGREGATION")
        self.assertEqual(row["dynamic_shape_family"], "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(row["dynamic_baseline_family"], "DYNAMIC_FILTER_SELECT_LIST_CLEANUP")
        self.assertEqual(row["dynamic_delivery_class"], "SAFE_BASELINE_NO_DIFF")


if __name__ == "__main__":
    unittest.main()
