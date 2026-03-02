from __future__ import annotations

import unittest
from pathlib import Path

from sqlopt.application.requests import AdvanceStepRequest, RunStatusRequest
from sqlopt.application import workflow_engine
from sqlopt.contracts import ContractValidator

ROOT = Path(__file__).resolve().parents[1]


class WorkflowEngineRequestsTest(unittest.TestCase):
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
                    "demo.user.find#v1": {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"}
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
        self.assertEqual(snapshot["current_sql_key"], "demo.user.find#v1")
        self.assertEqual(snapshot["next_action"], "resume")
        self.assertFalse(snapshot["complete"])

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
