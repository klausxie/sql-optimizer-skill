from __future__ import annotations

import unittest
from pathlib import Path

from sqlopt.application.requests import AdvanceStepRequest, RunStatusRequest
from sqlopt.application import workflow_engine
from sqlopt.contracts import ContractValidator

ROOT = Path(__file__).resolve().parents[3]


class WorkflowEngineRequestsTest(unittest.TestCase):
    def test_handler_registry_keeps_expected_phase_order(self) -> None:
        pre = [handler.__name__ for handler in workflow_engine.PRE_INDEX_HANDLERS]
        indexed = [handler.__name__ for handler in workflow_engine.INDEXED_HANDLERS]
        self.assertEqual(pre, ["_advance_preflight", "_advance_scan"])
        self.assertEqual(indexed, ["_advance_optimize", "_advance_validate", "_advance_patch_generate"])
        self.assertEqual(workflow_engine.REPORT_HANDLER.__name__, "_advance_report")

    def test_build_status_snapshot_uses_request_object(self) -> None:
        request = RunStatusRequest(
            run_id="run_demo",
            state={
                "current_phase": "optimize",
                "phase_status": {
                    "preflight": "DONE",
                    "scan": "DONE",
                    "optimize": "PENDING",
                    "validate": "PENDING",
                    "patch_generate": "PENDING",
                    "report": "PENDING",
                },
                "statements": {
                    "demo.user.find": {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"}
                },
                "attempts_by_phase": {"optimize": 1},
                "last_reason_code": None,
            },
            plan={"to_stage": "patch_generate"},
            meta={"status": "RUNNING"},
            config={"report": {"enabled": False}},
        )

        snapshot = workflow_engine.build_status_snapshot(request)

        self.assertEqual(snapshot["run_id"], "run_demo")
        self.assertEqual(snapshot["current_sql_key"], "demo.user.find")
        self.assertEqual(snapshot["next_action"], "resume")
        self.assertFalse(snapshot["complete"])

    def test_build_status_snapshot_marks_completed_run_for_report_rebuild(self) -> None:
        request = RunStatusRequest(
            run_id="run_demo",
            state={
                "current_phase": "report",
                "phase_status": {
                    "preflight": "DONE",
                    "scan": "DONE",
                    "optimize": "DONE",
                    "validate": "DONE",
                    "patch_generate": "DONE",
                    "report": "DONE",
                },
                "statements": {},
                "attempts_by_phase": {"report": 2},
                "report_rebuild_required": True,
                "last_reason_code": "REPORT_FAILED",
            },
            plan={"to_stage": "patch_generate"},
            meta={"status": "COMPLETED"},
            config={"report": {"enabled": True}},
        )

        snapshot = workflow_engine.build_status_snapshot(request)

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["next_action"], "report-rebuild")
        self.assertEqual(snapshot["run_status"], "COMPLETED")

    def test_build_status_snapshot_completed_run_has_no_follow_up_action(self) -> None:
        request = RunStatusRequest(
            run_id="run_done",
            state={
                "current_phase": "report",
                "phase_status": {
                    "preflight": "DONE",
                    "scan": "DONE",
                    "optimize": "DONE",
                    "validate": "DONE",
                    "patch_generate": "DONE",
                    "report": "DONE",
                },
                "statements": {},
                "attempts_by_phase": {"report": 1},
                "report_rebuild_required": False,
                "last_reason_code": None,
            },
            plan={"to_stage": "patch_generate"},
            meta={"status": "COMPLETED"},
            config={"report": {"enabled": True}},
        )

        snapshot = workflow_engine.build_status_snapshot(request)

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["next_action"], "none")

    def test_advance_one_step_wrapper_builds_request_object(self) -> None:
        captured: dict[str, object] = {}

        def fake_advance(request: AdvanceStepRequest) -> dict:
            captured["request"] = request
            return {"complete": False, "phase": "preflight"}

        original = workflow_engine.advance_one_step_request
        workflow_engine.advance_one_step_request = fake_advance
        try:
            result = workflow_engine.advance_one_step(
                ROOT,
                {"report": {"enabled": False}, "validate": {}},
                "preflight",
                ContractValidator(ROOT),
            )
        finally:
            workflow_engine.advance_one_step_request = original

        self.assertEqual(result, {"complete": False, "phase": "preflight"})
        request = captured["request"]
        self.assertIsInstance(request, AdvanceStepRequest)
        self.assertEqual(request.run_dir, ROOT)
        self.assertEqual(request.to_stage, "preflight")


if __name__ == "__main__":
    unittest.main()
