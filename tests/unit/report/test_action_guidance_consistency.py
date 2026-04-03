from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.application.diagnostics_summary import build_verify_payload
from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ReportInputs, ReportStateSnapshot


class ActionGuidanceConsistencyTest(unittest.TestCase):
    def test_report_keeps_template_rewrite_cases_in_inspect_mode(self) -> None:
        sql_key = "demo.user.findIncluded"
        acceptance_rows = [
            {
                "sqlKey": sql_key,
                "status": "PASS",
                "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                "perfComparison": {"reasonCodes": []},
                "riskFlags": [],
            }
        ]
        patch_rows = [
            {
                "sqlKey": sql_key,
                "statementKey": "demo.user.findIncluded",
                "applicable": None,
                "deliveryOutcome": {"tier": "PATCHABLE_WITH_REWRITE"},
            }
        ]
        inputs = ReportInputs(
            units=[{"sqlKey": sql_key}],
            proposals=[{"sqlKey": sql_key, "verdict": "CAN_IMPROVE", "issues": []}],
            acceptance=acceptance_rows,
            patches=patch_rows,
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )

        with tempfile.TemporaryDirectory(prefix="guidance_consistency_") as td:
            run_dir = Path(td)
            artifacts = build_report_artifacts("run_demo", "analyze", {"policy": {}, "runtime": {}, "llm": {"enabled": False}}, run_dir, inputs)
            verify_payload = build_verify_payload(
                "run_demo",
                run_dir,
                sql_key,
                None,
                True,
                [],
                acceptance_rows,
                patch_rows,
            )

        self.assertEqual(artifacts.report.next_action, "inspect")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "inspect")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "refactor-mapper")


if __name__ == "__main__":
    unittest.main()
