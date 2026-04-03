from __future__ import annotations

import unittest

from sqlopt.application.requests import RunStatusRequest
from sqlopt.application.status_resolver import StatusResolver
from sqlopt.application.workflow_definition import PHASE_POLICIES, STAGE_ORDER


class StatusResolverTest(unittest.TestCase):
    def _resolver(self) -> StatusResolver:
        return StatusResolver(stage_order=STAGE_ORDER, phase_policies=PHASE_POLICIES)

    def test_scan_target_is_complete_without_report_gating(self) -> None:
        resolver = self._resolver()
        result = resolver.resolve_status(
            RunStatusRequest(
                run_id="run_partial",
                state={
                    "current_phase": "report",
                    "phase_status": {
                        "preflight": "DONE",
                        "scan": "DONE",
                        "optimize": "PENDING",
                        "validate": "PENDING",
                        "patch_generate": "PENDING",
                        "report": "DONE",
                    },
                    "statements": {"demo.user.a": {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"}},
                    "attempts_by_phase": {},
                    "report_rebuild_required": False,
                },
                plan={"to_stage": "scan", "sql_keys": ["demo.user.a"]},
                meta={"status": "COMPLETED"},
                config={"report": {"enabled": True}},
            )
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.next_action, "none")


if __name__ == "__main__":
    unittest.main()
