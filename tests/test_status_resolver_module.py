from __future__ import annotations

import unittest

from sqlopt.application.requests import RunStatusRequest
from sqlopt.application.status_resolver import PhaseExecutionPolicy, StatusResolver


class StatusResolverModuleTest(unittest.TestCase):
    def _resolver(self) -> StatusResolver:
        return StatusResolver(
            stage_order=["diagnose", "optimize", "validate", "apply", "report"],
            phase_policies={
                "diagnose": PhaseExecutionPolicy("diagnose"),
                "optimize": PhaseExecutionPolicy("optimize"),
                "validate": PhaseExecutionPolicy("validate"),
                "apply": PhaseExecutionPolicy("apply"),
                "report": PhaseExecutionPolicy("report", allow_regenerate=True),
            },
        )

    def test_resolve_status_requires_resume_when_target_not_complete(self) -> None:
        resolver = self._resolver()
        result = resolver.resolve_status(
            RunStatusRequest(
                run_id="run_demo",
                state={
                    "current_phase": "validate",
                    "phase_status": {
                        "diagnose": "DONE",
                        "optimize": "DONE",
                        "validate": "PENDING",
                        "apply": "PENDING",
                        "report": "PENDING",
                    },
                    "statements": {
                        "demo#v1": {
                            "optimize": "DONE",
                            "validate": "PENDING",
                            "apply": "PENDING",
                        }
                    },
                },
                plan={"to_stage": "apply"},
                meta={"status": "RUNNING"},
                config={"report": {"enabled": True}},
            )
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.next_action, "resume")
        self.assertEqual(result.current_sql_key, "demo#v1")

    def test_resolve_status_returns_report_rebuild_for_completed_run(self) -> None:
        resolver = self._resolver()
        result = resolver.resolve_status(
            RunStatusRequest(
                run_id="run_done",
                state={
                    "current_phase": "report",
                    "phase_status": {
                        "diagnose": "DONE",
                        "optimize": "DONE",
                        "validate": "DONE",
                        "apply": "DONE",
                        "report": "DONE",
                    },
                    "report_rebuild_required": True,
                    "statements": {},
                },
                plan={"to_stage": "apply"},
                meta={"status": "COMPLETED"},
                config={"report": {"enabled": True}},
            )
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.next_action, "report-rebuild")


if __name__ == "__main__":
    unittest.main()
