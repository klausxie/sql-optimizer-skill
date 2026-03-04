from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.cli import _build_verify_payload
from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ReportInputs, ReportStateSnapshot


def _base_config() -> dict:
    return {
        "policy": {},
        "runtime": {
            "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
            "stage_retry_max": {"scan": 1, "report": 2},
            "stage_retry_backoff_ms": 50,
        },
        "llm": {"enabled": False},
    }


def _proposal(sql_key: str, *, score: int = 85, tier: str = "HIGH") -> dict:
    return {
        "sqlKey": sql_key,
        "issues": [{"code": "SELECT_STAR"}],
        "dbEvidenceSummary": {},
        "planSummary": {},
        "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
        "verdict": "CAN_IMPROVE",
        "actionability": {
            "score": score,
            "tier": tier,
            "autoPatchLikelihood": "HIGH",
            "reasons": [],
            "blockedBy": [],
        },
    }


def _render_outputs(
    *,
    sql_key: str,
    acceptance_rows: list[dict],
    patch_rows: list[dict],
    verification_rows: list[dict],
) -> tuple[dict, dict]:
    inputs = ReportInputs(
        units=[{"sqlKey": sql_key}],
        proposals=[_proposal(sql_key)],
        acceptance=acceptance_rows,
        patches=patch_rows,
        state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
        manifest_rows=[],
        verification_rows=verification_rows,
    )
    with tempfile.TemporaryDirectory(prefix="sqlopt_output_guidance_") as td:
        run_dir = Path(td)
        artifacts = build_report_artifacts("run_demo", "analyze", _base_config(), run_dir, inputs)
        verify_payload = _build_verify_payload(
            "run_demo",
            run_dir,
            sql_key,
            None,
            True,
            verification_rows,
            acceptance_rows,
            patch_rows,
        )
    return artifacts.report.to_contract(), verify_payload


class OutputGuidanceConsistencyTest(unittest.TestCase):
    def test_critical_gap_overrides_ready_to_apply_guidance(self) -> None:
        sql_key = "demo.user.findUsers#v1"
        report, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "PASS",
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": []},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "PASS"},
                    },
                }
            ],
            patch_rows=[
                {
                    "sqlKey": sql_key,
                    "statementKey": "demo.user.findUsers",
                    "applicable": True,
                    "deliveryOutcome": {"tier": "READY_TO_APPLY"},
                }
            ],
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

        self.assertEqual(report["summary"]["next_actions"][0]["action_id"], "review-evidence")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "review-evidence")
        self.assertEqual(report["summary"]["next_actions"][0]["reason"], verify_payload["recommended_next_step"]["reason"])
        self.assertEqual(report["stats"]["top_actionable_sql"][0]["evidence_state"], "CRITICAL_GAP")
        self.assertEqual(verify_payload["evidence_state"], "CRITICAL_GAP")
        # 检查 why_now 包含证据相关关键词（中文或英文）
        why_now_report = report["stats"]["top_actionable_sql"][0]["why_now"]
        why_now_verify = verify_payload["why_now"]
        self.assertTrue(
            "证据" in why_now_report or "evidence" in why_now_report,
            f"why_now should mention evidence: {why_now_report}"
        )
        self.assertTrue(
            "证据" in why_now_verify or "evidence" in why_now_verify,
            f"why_now should mention evidence: {why_now_verify}"
        )

    def test_degraded_db_paths_keep_reason_aligned(self) -> None:
        sql_key = "demo.user.listUsers#v1"
        report, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "NEED_MORE_PARAMS",
                    "decisionLayers": {
                        "evidence": {"degraded": True, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                        "delivery": {"tier": "READY"},
                        "acceptance": {
                            "status": "NEED_MORE_PARAMS",
                            "feedbackReasonCode": "VALIDATE_PARAM_INSUFFICIENT",
                        },
                    },
                }
            ],
            patch_rows=[],
            verification_rows=[],
        )

        self.assertEqual(report["summary"]["next_actions"][0]["action_id"], "check-db")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "restore-db-validation")
        self.assertEqual(report["summary"]["next_actions"][0]["reason"], verify_payload["recommended_next_step"]["reason"])
        self.assertEqual(report["stats"]["top_actionable_sql"][0]["evidence_state"], "DEGRADED")
        self.assertEqual(verify_payload["evidence_state"], "DEGRADED")
        # 检查 why_now 包含 DB/数据库相关关键词
        why_now_report = report["stats"]["top_actionable_sql"][0]["why_now"]
        why_now_verify = verify_payload["why_now"]
        self.assertTrue(
            "DB" in why_now_report or "db" in why_now_report.lower() or "数据库" in why_now_report,
            f"why_now should mention DB: {why_now_report}"
        )
        self.assertTrue(
            "DB" in why_now_verify or "db" in why_now_verify.lower() or "数据库" in why_now_verify,
            f"why_now should mention DB: {why_now_verify}"
        )

    def test_ready_to_apply_paths_share_why_now_language(self) -> None:
        sql_key = "demo.user.applyPatch#v1"
        report, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "PASS",
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": []},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "PASS"},
                    },
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

        self.assertEqual(report["summary"]["next_actions"][0]["action_id"], "apply")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "apply")
        self.assertEqual(report["summary"]["next_actions"][0]["reason"], verify_payload["recommended_next_step"]["reason"])
        # why_now 可能因语言不同而不同，但应该包含类似的概念（最快/安全/收益）
        why_now_report = report["stats"]["top_actionable_sql"][0]["why_now"]
        why_now_verify = verify_payload["why_now"]
        # 检查包含"最快"或"fastest"关键词
        self.assertTrue(
            "最快" in why_now_report or "fastest" in why_now_report.lower(),
            f"why_now should mention fastest: {why_now_report}"
        )
        self.assertTrue(
            "最快" in why_now_verify or "fastest" in why_now_verify.lower(),
            f"why_now should mention fastest: {why_now_verify}"
        )


if __name__ == "__main__":
    unittest.main()
