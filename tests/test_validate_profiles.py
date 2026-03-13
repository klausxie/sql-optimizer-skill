from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.platforms.base import PlatformCapabilities
from sqlopt.platforms.sql.models import AcceptanceDecision
from sqlopt.platforms.sql.validator_sql import _normalize_dml_clean_blocker_decision, validate_proposal


class ValidateProfilesTest(unittest.TestCase):
    def test_dml_clean_blocker_is_normalized_to_pass(self) -> None:
        decision = AcceptanceDecision(
            status="NEED_MORE_PARAMS",
            feedback={"reason_code": "VALIDATE_SEMANTIC_ERROR"},
            warnings=[],
            reason_codes=["VALIDATE_SEMANTIC_ERROR"],
        )

        normalized = _normalize_dml_clean_blocker_decision(
            sql_unit={"sqlKey": "demo.user.advanced.updateUserSelective#v9", "statementType": "UPDATE"},
            decision=decision,
            semantic_equivalence={"status": "PASS"},
            rewrite_facts={"effectiveChange": False},
            patchability={
                "blockingReason": "PATCH_NO_EFFECTIVE_CHANGE",
                "dynamicBlockingReason": "DYNAMIC_SET_CLAUSE",
            },
        )

        self.assertEqual(normalized.status, "PASS")
        self.assertIsNone(normalized.feedback)
        self.assertNotIn("VALIDATE_SEMANTIC_ERROR", normalized.reason_codes)
        self.assertIn("VALIDATE_DML_COMPARE_SKIPPED_WARN", normalized.warnings)

    def test_dml_perf_only_clean_blocker_is_normalized_to_pass(self) -> None:
        decision = AcceptanceDecision(
            status="NEED_MORE_PARAMS",
            feedback={"reason_code": "VALIDATE_PERF_NOT_IMPROVED"},
            warnings=[],
            reason_codes=["VALIDATE_PERF_NOT_IMPROVED"],
        )

        normalized = _normalize_dml_clean_blocker_decision(
            sql_unit={"sqlKey": "demo.order.harness.updateOrderStatusByNos#v6", "statementType": "UPDATE"},
            decision=decision,
            semantic_equivalence={"status": "PASS"},
            rewrite_facts={"effectiveChange": False},
            patchability={
                "blockingReason": "PATCH_NO_EFFECTIVE_CHANGE",
                "dynamicBlockingReason": "FOREACH_COLLECTION_PREDICATE",
            },
        )

        self.assertEqual(normalized.status, "PASS")
        self.assertIsNone(normalized.feedback)
        self.assertNotIn("VALIDATE_PERF_NOT_IMPROVED", normalized.reason_codes)
        self.assertIn("VALIDATE_DML_COMPARE_SKIPPED_WARN", normalized.warnings)

    def test_balanced_pass_with_warn_when_not_improved(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT id, name FROM users", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT id, name FROM users ORDER BY created_at DESC"}],
            "suggestions": [],
        }
        config = {"db": {"platform": "postgresql", "dsn": "postgresql://dummy"}, "validate": {"validation_profile": "balanced"}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 10.0},
                "reasonCodes": ["TOTAL_COST_NOT_REDUCED"],
                "improved": False,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_balanced_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["status"], "PASS")
        self.assertIn("VALIDATE_PERF_NOT_IMPROVED_WARN", result.get("warnings", []))
        self.assertEqual(result.get("decisionLayers", {}).get("acceptance", {}).get("status"), "PASS")
        self.assertEqual(result.get("decisionLayers", {}).get("acceptance", {}).get("validationProfile"), "balanced")
        self.assertEqual((result.get("semanticEquivalence") or {}).get("status"), "UNCERTAIN")
        self.assertEqual((result.get("semanticEquivalence") or {}).get("confidence"), "MEDIUM")
        self.assertEqual((result.get("semanticEquivalence") or {}).get("evidenceLevel"), "DB_COUNT")

    def test_semantic_error_is_need_more_params(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT id, name FROM users", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT id, name FROM users ORDER BY created_at DESC"}],
            "suggestions": [],
        }
        config = {"db": {"platform": "postgresql", "dsn": "postgresql://dummy"}, "validate": {"validation_profile": "balanced"}, "policy": {}}

        def fake_semantics(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "timeout"},
                "evidenceRefs": [],
            }

        def fake_plan(_cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="validate_semantic_error_") as td:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", side_effect=fake_semantics), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan", side_effect=fake_plan
            ):
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        self.assertEqual(result["status"], "NEED_MORE_PARAMS")
        self.assertEqual((result.get("feedback") or {}).get("reason_code"), "VALIDATE_SEMANTIC_ERROR")
        self.assertEqual((result.get("semanticEquivalence") or {}).get("status"), "UNCERTAIN")
        self.assertEqual((result.get("semanticEquivalence") or {}).get("confidence"), "LOW")

    def test_dollar_substitution_balanced_is_need_more_params(self) -> None:
        sql_unit = {"sqlKey": "demo.user.findUsers#v1", "sql": "SELECT * FROM users ORDER BY ${orderBy}", "statementType": "SELECT"}
        result = validate_proposal(
            sql_unit,
            proposal={"llmCandidates": [], "suggestions": []},
            db_reachable=True,
            config={"validate": {"validation_profile": "balanced"}},
            evidence_dir=Path(tempfile.gettempdir()),
        )
        self.assertEqual(result["status"], "NEED_MORE_PARAMS")
        self.assertIn("DOLLAR_SUBSTITUTION", result.get("riskFlags", []))
        self.assertEqual(result.get("decisionLayers", {}).get("feasibility", {}).get("phase"), "security_block")
        self.assertEqual((result.get("repairability") or {}).get("status"), "REPAIRABLE")
        self.assertEqual(result.get("rewriteSafetyLevel"), "REVIEW")
        self.assertGreaterEqual(len(result.get("repairHints") or []), 1)

    def test_dollar_substitution_strict_is_fail(self) -> None:
        sql_unit = {"sqlKey": "demo.user.findUsers#v1", "sql": "SELECT * FROM users ORDER BY ${orderBy}", "statementType": "SELECT"}
        result = validate_proposal(
            sql_unit,
            proposal={"llmCandidates": [], "suggestions": []},
            db_reachable=True,
            config={"validate": {"validation_profile": "strict"}},
            evidence_dir=Path(tempfile.gettempdir()),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result.get("decisionLayers", {}).get("acceptance", {}).get("validationProfile"), "strict")
        self.assertEqual((result.get("repairability") or {}).get("status"), "BLOCKED")
        self.assertEqual(result.get("rewriteSafetyLevel"), "BLOCKED")

    def test_plan_and_semantic_compare_are_capability_gated(self) -> None:
        sql_unit = {"sqlKey": "demo.user.listUsers#v1", "sql": "SELECT id, name FROM users", "statementType": "SELECT"}
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT id, name FROM users ORDER BY created_at DESC"}],
            "suggestions": [],
        }
        config = {"db": {"dsn": "postgresql://dummy", "platform": "postgresql"}, "validate": {"validation_profile": "balanced"}, "policy": {}}

        with tempfile.TemporaryDirectory(prefix="validate_capability_gate_") as td:
            with patch(
                "sqlopt.platforms.sql.validation_strategy.get_platform_capabilities",
                return_value=PlatformCapabilities(
                    supports_connectivity_check=True,
                    supports_plan_compare=False,
                    supports_semantic_compare=False,
                    supports_sql_evidence=True,
                ),
            ), patch("sqlopt.platforms.sql.validator_sql.compare_semantics") as semantics_mock, patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan"
            ) as plan_mock:
                result = validate_proposal(sql_unit, proposal, True, config=config, evidence_dir=Path(td))

        semantics_mock.assert_not_called()
        plan_mock.assert_not_called()
        self.assertFalse(result["equivalence"]["checked"])
        self.assertFalse(result["perfComparison"]["checked"])
        self.assertIn("VALIDATE_PLAN_COMPARE_DISABLED", result["perfComparison"]["reasonCodes"])
        self.assertEqual(result["status"], "NEED_MORE_PARAMS")
        self.assertTrue(result.get("decisionLayers", {}).get("evidence", {}).get("degraded"))


if __name__ == "__main__":
    unittest.main()
