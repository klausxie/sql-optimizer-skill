from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.application.diagnostics_summary import build_verify_payload
from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ReportInputs, ReportStateSnapshot


def _render_outputs(
    *,
    sql_key: str,
    acceptance_rows: list[dict],
    patch_rows: list[dict],
    verification_rows: list[dict],
) -> tuple[object, dict]:
    inputs = ReportInputs(
        units=[{"sqlKey": sql_key}],
        proposals=[{"sqlKey": sql_key, "verdict": "CAN_IMPROVE", "issues": []}],
        acceptance=acceptance_rows,
        patches=patch_rows,
        state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
        manifest_rows=[],
        verification_rows=verification_rows,
    )
    with tempfile.TemporaryDirectory(prefix="sqlopt_output_guidance_") as td:
        run_dir = Path(td)
        artifacts = build_report_artifacts("run_demo", "analyze", {"policy": {}, "runtime": {}, "llm": {"enabled": False}}, run_dir, inputs)
        verify_payload = build_verify_payload(
            "run_demo",
            run_dir,
            sql_key,
            None,
            True,
            verification_rows,
            acceptance_rows,
            patch_rows,
        )
    return artifacts, verify_payload


class OutputGuidanceConsistencyTest(unittest.TestCase):
    def test_critical_gap_keeps_report_in_inspect_mode(self) -> None:
        sql_key = "demo.user.findUsers"
        artifacts, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[{"sqlKey": sql_key, "status": "PASS", "decisionLayers": {"delivery": {"tier": "READY"}}}],
            patch_rows=[{"sqlKey": sql_key, "statementKey": "demo.user.findUsers", "applicable": True}],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": sql_key,
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

        self.assertEqual(artifacts.report.next_action, "inspect")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "review-evidence")
        self.assertEqual(verify_payload["evidence_state"], "CRITICAL_GAP")

    def test_ready_to_apply_keeps_report_in_apply_mode(self) -> None:
        sql_key = "demo.user.applyPatch"
        artifacts, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "PASS",
                    "equivalence": {"checked": True, "evidenceRefs": ["evidence/db.json"]},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                }
            ],
            patch_rows=[
                {
                    "sqlKey": sql_key,
                    "statementKey": "demo.user.applyPatch",
                    "applicable": True,
                    "deliveryOutcome": {"tier": "READY_TO_APPLY"},
                }
            ],
            verification_rows=[],
        )

        self.assertEqual(artifacts.report.next_action, "apply")
        self.assertEqual(artifacts.next_actions[0]["action_id"], "apply")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "apply")

    def test_security_block_still_surfaces_in_verify_payload(self) -> None:
        sql_key = "demo.user.findUsersSecurity"
        _artifacts, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"]},
                        "delivery": {"tier": "BLOCKED"},
                        "acceptance": {"status": "NEED_MORE_PARAMS", "feedbackReasonCode": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"},
                    },
                }
            ],
            patch_rows=[],
            verification_rows=[],
        )

        self.assertEqual(verify_payload["blocker_primary_code"], "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "remove-dollar")


if __name__ == "__main__":
    unittest.main()
