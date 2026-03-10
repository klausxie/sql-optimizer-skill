from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.stages import patch_generate

ROOT = Path(__file__).resolve().parents[1]


class PatchGenerateOrchestrationTest(unittest.TestCase):
    def _prepare_run_dir(self, acceptance: dict) -> Path:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_patch_orchestration_")
        self.addCleanup(td.cleanup)
        run_dir = Path(td.name)
        (run_dir / "pipeline" / "validate").mkdir(parents=True, exist_ok=True)
        (run_dir / "pipeline" / "patch_generate").mkdir(parents=True, exist_ok=True)
        (run_dir / "pipeline" / "manifest.jsonl").write_text("", encoding="utf-8")
        (run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").write_text(
            json.dumps(acceptance, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return run_dir

    def _validator(self) -> ContractValidator:
        return ContractValidator(ROOT)

    def test_missing_statement_locator_short_circuits_generation(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {"sqlKey": "demo.user.find#v1", "statementType": "SELECT", "sql": "SELECT * FROM users", "locators": {}}

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_LOCATOR_AMBIGUOUS")

    def test_non_pass_acceptance_short_circuits_generation(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "REJECT",
            "rewrittenSql": "SELECT id FROM users",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "locators": {"statementId": "findUsers"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_CONFLICT_NO_CLEAR_WINNER")
        self.assertTrue(patch_row["diffSummary"]["skipped"])

    def test_template_plan_error_prevents_unified_patch_attempt(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "xmlPath": str(ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"),
            "locators": {"statementId": "listUsersSorted"},
        }

        with patch(
            "sqlopt.stages.patch_generate._build_template_plan_patch",
            return_value=(None, 0, {"code": "PATCH_TEMPLATE_MATERIALIZATION_MISSING", "message": "missing replay verification"}),
        ) as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_called_once()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_TEMPLATE_MATERIALIZATION_MISSING")

    def test_dynamic_features_skip_before_unified_patch(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "dynamicFeatures": ["FOREACH"],
            "xmlPath": str(ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"),
            "locators": {"statementId": "findByList"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(None, 0, None)) as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_called_once()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE")

    def test_semantic_gate_not_pass_short_circuits_generation(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "semanticEquivalence": {"status": "UNCERTAIN"},
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "locators": {"statementId": "findUsers"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS")
        self.assertTrue(patch_row["diffSummary"]["skipped"])

    def test_semantic_low_confidence_short_circuits_generation(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "semanticEquivalence": {"status": "PASS", "confidence": "LOW"},
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "locators": {"statementId": "findUsers"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_SEMANTIC_CONFIDENCE_LOW")
        self.assertTrue(patch_row["diffSummary"]["skipped"])

    def test_no_effective_change_short_circuits_before_patch_build(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "  SELECT   *   FROM users   ",
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
            "selectedCandidateId": "c1",
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users",
            "xmlPath": str(ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"),
            "locators": {"statementId": "listUsersSorted"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_NO_EFFECTIVE_CHANGE")
        self.assertTrue(patch_row["diffSummary"]["skipped"])
        patch_file = run_dir / "pipeline" / "patch_generate" / "files" / "demo.user.find#v1.patch"
        self.assertFalse(patch_file.exists())


if __name__ == "__main__":
    unittest.main()
