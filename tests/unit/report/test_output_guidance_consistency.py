from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.application.diagnostics_summary import build_verify_payload
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
) -> tuple[object, dict, dict]:
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
    return artifacts, artifacts.report.to_contract(), verify_payload


class OutputGuidanceConsistencyTest(unittest.TestCase):
    def test_critical_gap_overrides_ready_to_apply_guidance(self) -> None:
        sql_key = "demo.user.findUsers#v1"
        artifacts, report, verify_payload = _render_outputs(
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

        self.assertEqual(artifacts.next_actions[0]["action_id"], "review-evidence")
        self.assertEqual(report["next_action"], "inspect")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "review-evidence")
        self.assertEqual(artifacts.next_actions[0]["reason"], verify_payload["recommended_next_step"]["reason"])
        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_state"], "CRITICAL_GAP")
        self.assertEqual(verify_payload["evidence_state"], "CRITICAL_GAP")
        self.assertIn("semantic_gate_status", verify_payload)
        self.assertIn("semantic_unupgraded_reason", verify_payload)
        self.assertIn("semantic_blocked_reason", verify_payload)
        # 检查 why_now 包含证据相关关键词（中文或英文）
        why_now_report = artifacts.report.stats["top_actionable_sql"][0]["why_now"]
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
        artifacts, report, verify_payload = _render_outputs(
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

        self.assertEqual(artifacts.next_actions[0]["action_id"], "check-db")
        self.assertEqual(report["next_action"], "inspect")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "restore-db-validation")
        self.assertEqual(artifacts.next_actions[0]["reason"], verify_payload["recommended_next_step"]["reason"])
        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_state"], "DEGRADED")
        self.assertEqual(verify_payload["evidence_state"], "DEGRADED")
        self.assertIn("semantic_gate_confidence", verify_payload)
        # 检查 why_now 包含 DB/数据库相关关键词
        why_now_report = artifacts.report.stats["top_actionable_sql"][0]["why_now"]
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
        artifacts, report, verify_payload = _render_outputs(
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

        self.assertEqual(artifacts.next_actions[0]["action_id"], "apply")
        self.assertEqual(report["next_action"], "apply")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "apply")
        self.assertEqual(artifacts.next_actions[0]["reason"], verify_payload["recommended_next_step"]["reason"])
        self.assertIn("semantic_confidence_upgraded", verify_payload)
        # why_now 可能因语言不同而不同，但应该包含类似的概念（最快/安全/收益）
        why_now_report = artifacts.report.stats["top_actionable_sql"][0]["why_now"]
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

    def test_semantic_low_confidence_prefers_review_evidence_action(self) -> None:
        sql_key = "demo.user.lowConfidence#v1"
        artifacts, _report, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "PASS",
                    "semanticEquivalence": {
                        "status": "PASS",
                        "confidence": "LOW",
                        "confidenceBeforeUpgrade": "LOW",
                        "confidenceUpgradeApplied": False,
                        "confidenceUpgradeReasons": [],
                        "confidenceUpgradeEvidenceSources": [],
                    },
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": []},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "PASS"},
                    },
                }
            ],
            patch_rows=[],
            verification_rows=[],
        )

        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["semantic_blocked_reason"], "VALIDATE_SEMANTIC_CONFIDENCE_LOW")
        self.assertEqual(verify_payload["semantic_blocked_reason"], "VALIDATE_SEMANTIC_CONFIDENCE_LOW")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "review-evidence")
        self.assertIn("semantic confidence is low", verify_payload["decision_summary"])
        self.assertIn("evidence strength", verify_payload["why_now"])

    def test_security_block_sets_primary_blocker_and_remove_dollar_action(self) -> None:
        sql_key = "demo.user.findUsers#v2"
        artifacts, _report, verify_payload = _render_outputs(
            sql_key=sql_key,
            acceptance_rows=[
                {
                    "sqlKey": sql_key,
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"},
                    "equivalence": {"checked": True, "method": "static", "evidenceRefs": []},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "UNKNOWN"},
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
        top = artifacts.report.stats["top_actionable_sql"][0]
        self.assertEqual(top["blocker_primary_code"], "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION")
        self.assertEqual(top["evidence_availability"], "MISSING")
        self.assertEqual(top["evidence_missing_reason"], "SKIPPED_BY_SECURITY_BLOCK")
        self.assertIn("${}", top["summary"])
        self.assertEqual(verify_payload["blocker_primary_code"], "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION")
        self.assertEqual(verify_payload["evidence_missing_reason"], "SKIPPED_BY_SECURITY_BLOCK")
        self.assertEqual(verify_payload["recommended_next_step"]["action"], "remove-dollar")


if __name__ == "__main__":
    unittest.main()
