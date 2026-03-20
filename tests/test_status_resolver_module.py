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

    def test_resolve_status_returns_none_when_target_complete(self) -> None:
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
                    "statements": {},
                },
                plan={"to_stage": "apply"},
                meta={"status": "COMPLETED"},
                config={"report": {"enabled": True}},
            )
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.next_action, "none")

    def test_pending_by_phase_uses_stage_order_for_v9_pipeline(self) -> None:
        resolver = StatusResolver(
            stage_order=["init", "parse", "recognition", "optimize", "patch"],
            phase_policies={
                "init": PhaseExecutionPolicy("init"),
                "parse": PhaseExecutionPolicy("parse"),
                "recognition": PhaseExecutionPolicy("recognition"),
                "optimize": PhaseExecutionPolicy("optimize"),
                "patch": PhaseExecutionPolicy("patch"),
            },
        )

        counts = resolver.pending_by_phase(
            {
                "statements": {
                    "demo#v1": {
                        "recognition": "DONE",
                        "optimize": "PENDING",
                        "patch": "PENDING",
                    }
                }
            }
        )

        self.assertEqual(
            counts,
            {
                "init": 0,
                "parse": 0,
                "recognition": 0,
                "optimize": 1,
                "patch": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
