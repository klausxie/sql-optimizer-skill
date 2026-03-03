from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.cli import _build_verify_payload
from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ReportInputs, ReportStateSnapshot


class ActionGuidanceConsistencyTest(unittest.TestCase):
    def test_report_and_verify_align_on_template_rewrite_guidance(self) -> None:
        acceptance_rows = [
            {
                "sqlKey": "demo.user.findIncluded#v1",
                "status": "PASS",
                "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                "perfComparison": {"reasonCodes": []},
                "riskFlags": [],
            }
        ]
        patch_rows = [
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
        ]
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
            acceptance=acceptance_rows,
            patches=patch_rows,
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

        with tempfile.TemporaryDirectory(prefix="guidance_consistency_") as td:
            run_dir = Path(td)
            artifacts = build_report_artifacts("run_demo", "analyze", config, run_dir, inputs)
            verify_payload = _build_verify_payload(
                "run_demo",
                run_dir,
                "demo.user.findIncluded#v1",
                None,
                True,
                [],
                acceptance_rows,
                patch_rows,
            )

        self.assertEqual(artifacts.next_actions[0]["action_id"], "refactor-mapper")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "refactor-mapper")
        self.assertEqual(artifacts.next_actions[0]["reason"], verify_payload["recommended_next_step"]["reason"])


if __name__ == "__main__":
    unittest.main()
