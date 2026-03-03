from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_loader import ReportInputs


class ReportBuilderTest(unittest.TestCase):
    def test_build_report_artifacts_aggregates_failures_and_phase_coverage(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT"},
                    "perfComparison": {"reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "riskFlags": [],
                }
            ],
            patches=[],
            state={
                "phase_status": {"preflight": "DONE", "scan": "DONE", "report": "DONE"},
                "attempts_by_phase": {"report": 1},
            },
            manifest_rows=[
                {
                    "stage": "preflight",
                    "event": "failed",
                    "payload": {"reason_code": "PREFLIGHT_SCANNER_MISSING"},
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

        self.assertEqual(artifacts.report["stats"]["sql_units"], 1)
        self.assertEqual(artifacts.report["stats"]["acceptance_need_more_params"], 1)
        self.assertEqual(artifacts.report["stats"]["preflight_failure_count"], 1)
        self.assertEqual(artifacts.report["stats"]["pipeline_coverage"]["report"], "DONE")
        self.assertEqual(len(artifacts.failures), 2)
        self.assertIn("validate", artifacts.report["stats"]["phase_reason_code_counts"])
        self.assertIn("preflight", artifacts.report["stats"]["phase_reason_code_counts"])
        self.assertEqual(artifacts.topology["runtime_policy"]["stage_timeout_ms"]["report"], 300)
        self.assertEqual(artifacts.health["report_json"], str(Path(td) / "report.json"))


if __name__ == "__main__":
    unittest.main()
