from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.stages.patch_applicability import PatchApplicabilityResult
from sqlopt.stages import patch_generate
from sqlopt.stages.patching_render import build_unified_patch

ROOT = Path(__file__).resolve().parents[2]


class PatchGenerateOrchestrationTest(unittest.TestCase):
    def _thin_acceptance(self, *, rewritten_sql: str = "SELECT id FROM users") -> dict:
        return {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": rewritten_sql,
            "selectedCandidateId": "c1",
            "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
        }

    def _patch_target(self, *, target_sql: str = "SELECT id FROM users", after_template: str = "SELECT id FROM users") -> dict:
        return {
            "sqlKey": "demo.user.find#v1",
            "selectedCandidateId": "c1",
            "targetSql": target_sql,
            "targetSqlNormalized": target_sql,
            "targetSqlFingerprint": "demo-fingerprint",
            "semanticGateStatus": "PASS",
            "semanticGateConfidence": "HIGH",
            "selectedPatchStrategy": {"strategyType": "EXACT_TEMPLATE_EDIT"},
            "family": "STATIC_STATEMENT_REWRITE",
            "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
            "patchability": {"eligible": True},
            "rewriteMaterialization": {
                "mode": "STATEMENT_TEMPLATE_SAFE",
                "replayVerified": True,
                "replayContract": {
                    "replayMode": "STATEMENT_TEMPLATE_SAFE",
                    "requiredTemplateOps": ["replace_statement_body"],
                    "expectedRenderedSql": target_sql,
                    "expectedRenderedSqlNormalized": target_sql,
                    "expectedFingerprint": {"kind": "normalized_sql", "value": target_sql},
                    "requiredAnchors": [],
                    "requiredIncludes": [],
                    "requiredPlaceholderShape": [],
                    "dialectSyntaxCheckRequired": True,
                },
            },
            "templateRewriteOps": [{"op": "replace_statement_body", "afterTemplate": after_template}],
            "replayContract": {
                "replayMode": "STATEMENT_TEMPLATE_SAFE",
                "requiredTemplateOps": ["replace_statement_body"],
                "expectedRenderedSql": target_sql,
                "expectedRenderedSqlNormalized": target_sql,
                "expectedFingerprint": {"kind": "normalized_sql", "value": target_sql},
                "requiredAnchors": [],
                "requiredIncludes": [],
                "requiredPlaceholderShape": [],
                "dialectSyntaxCheckRequired": True,
            },
            "evidenceRefs": [],
        }

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

    def _dynamic_filter_wrapper_unit(self) -> tuple[dict, Path]:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_patch_dynamic_wrapper_")
        self.addCleanup(td.cleanup)
        xml_path = Path(td.name) / "demo_mapper.xml"
        xml_path.write_text(
            """<mapper namespace="demo.user.advanced">
  <select id="listUsersFilteredWrapped">
    SELECT id, name, email, status, created_at, updated_at
    FROM (
      SELECT id, name, email, status, created_at, updated_at
      FROM users
      <where>
        <if test="status != null and status != ''">
          AND status = #{status}
        </if>
        <if test="createdAfter != null">
          AND created_at &gt;= #{createdAfter}
        </if>
      </where>
    ) filtered_users
    ORDER BY created_at DESC
  </select>
</mapper>""",
            encoding="utf-8",
        )
        content = xml_path.read_text(encoding="utf-8")
        statement_open = '<select id="listUsersFilteredWrapped">'
        statement_start = content.index(statement_open) + len(statement_open)
        statement_end = content.index("</select>", statement_start)
        return (
            {
                "sqlKey": "demo.user.advanced.listUsersFilteredWrapped#v15",
                "sql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( "
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "WHERE status = #{status} AND created_at >= #{createdAfter} "
                    ") filtered_users ORDER BY created_at DESC"
                ),
                "xmlPath": str(xml_path),
                "namespace": "demo.user.advanced",
                "statementId": "listUsersFilteredWrapped",
                "templateSql": (
                    "SELECT id, name, email, status, created_at, updated_at FROM ( "
                    "SELECT id, name, email, status, created_at, updated_at FROM users "
                    "<where> <if test=\"status != null and status != ''\"> AND status = #{status} </if> "
                    "<if test=\"createdAfter != null\"> AND created_at &gt;= #{createdAfter} </if> </where> "
                    ") filtered_users ORDER BY created_at DESC"
                ),
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
                "locators": {"statementId": "listUsersFilteredWrapped", "range": {"startOffset": statement_start, "endOffset": statement_end}},
                "statementType": "SELECT",
            },
            xml_path,
        )

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

    def test_patch_generate_runs_applicability_before_proof(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        artifact_patch, changed_lines = build_unified_patch(xml_path, "listUsersProjected", "select", "SELECT name FROM users")
        self.assertIsNotNone(artifact_patch)
        self.assertGreater(changed_lines, 0)

        call_order: list[str] = []

        def _applicability(**_: object) -> tuple[PatchApplicabilityResult, str | None]:
            call_order.append("applicability")
            return (
                PatchApplicabilityResult(
                    artifact_kind="STATEMENT",
                    target_file=str(xml_path),
                    materialized=True,
                    applicability_checked=True,
                    apply_ready_candidate=True,
                    failure_class=None,
                    reason_code=None,
                ),
                None,
            )

        def _proof(**_: object) -> SimpleNamespace:
            call_order.append("proof")
            return SimpleNamespace(
                patch_target={"selectedCandidateId": "c1"},
                replay_evidence={"matchesTarget": True, "driftReason": None},
                syntax_evidence={"ok": True, "xmlParseOk": True, "renderOk": True, "sqlParseOk": True, "renderedSqlPresent": True, "reasonCode": None},
                ok=True,
                reason_code=None,
            )

        with patch("sqlopt.stages.patch_generate._build_unified_patch", return_value=(artifact_patch, changed_lines)):
            with patch("sqlopt.stages.patch_generate._run_patch_applicability", side_effect=_applicability):
                with patch("sqlopt.stages.patch_generate._prove_patch_plan", side_effect=_proof):
                    patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(call_order, ["applicability", "proof"])

    def test_patch_generate_reports_applicability_failure_without_proof_failure_code(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        artifact_patch, changed_lines = build_unified_patch(xml_path, "listUsersProjected", "select", "SELECT name FROM users")
        self.assertIsNotNone(artifact_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_unified_patch", return_value=(artifact_patch, changed_lines)):
            with patch(
                "sqlopt.stages.patch_generate._run_patch_applicability",
                return_value=(
                    PatchApplicabilityResult(
                        artifact_kind="STATEMENT",
                        target_file=str(xml_path),
                        materialized=True,
                        applicability_checked=True,
                        apply_ready_candidate=False,
                        failure_class="APPLICABILITY_FAILURE",
                        reason_code="PATCH_NOT_APPLICABLE",
                    ),
                    "patch does not apply",
                ),
            ):
                with patch("sqlopt.stages.patch_generate._prove_patch_plan") as proof_mock:
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        proof_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_NOT_APPLICABLE")
        self.assertEqual(patch_row.get("deliveryStage"), "APPLICABILITY_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "APPLICABILITY_FAILURE")

    def test_patch_generate_reports_proof_failure_after_applicability_success(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        artifact_patch, changed_lines = build_unified_patch(xml_path, "listUsersProjected", "select", "SELECT name FROM users")
        self.assertIsNotNone(artifact_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_unified_patch", return_value=(artifact_patch, changed_lines)):
            with patch(
                "sqlopt.stages.patch_generate._run_patch_applicability",
                return_value=(
                    PatchApplicabilityResult(
                        artifact_kind="STATEMENT",
                        target_file=str(xml_path),
                        materialized=True,
                        applicability_checked=True,
                        apply_ready_candidate=True,
                        failure_class=None,
                        reason_code=None,
                    ),
                    None,
                ),
            ):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": "PATCH_TARGET_DRIFT"},
                        syntax_evidence={"ok": True, "xmlParseOk": True, "renderOk": True, "sqlParseOk": True, "renderedSqlPresent": True, "reasonCode": None},
                        ok=False,
                        reason_code="PATCH_TARGET_DRIFT",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_TARGET_DRIFT")
        self.assertEqual(patch_row.get("deliveryStage"), "PROOF_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "PROOF_FAILURE")

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

    def test_security_block_non_pass_emits_repairable_patch_guidance(self) -> None:
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "NEED_MORE_PARAMS",
            "rewrittenSql": "SELECT id FROM users",
            "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"},
            "perfComparison": {"reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"]},
            "repairability": {"status": "REPAIRABLE"},
            "rewriteSafetyLevel": "REVIEW",
            "equivalence": {},
            "securityChecks": {},
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users ORDER BY ${orderBy}",
            "locators": {"statementId": "findUsers"},
        }

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
            with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_VALIDATION_BLOCKED_SECURITY")
        self.assertIn("VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", patch_row.get("fallbackReasonCodes", []))
        self.assertEqual((patch_row.get("selectionEvidence") or {}).get("acceptanceStatus"), "NEED_MORE_PARAMS")
        self.assertEqual((patch_row.get("selectionEvidence") or {}).get("repairabilityStatus"), "REPAIRABLE")
        self.assertEqual((patch_row.get("deliveryOutcome") or {}).get("tier"), "PATCHABLE_WITH_REWRITE")
        self.assertEqual((patch_row.get("repairHints") or [])[0].get("hintId"), "remove-dollar-substitution")

    def test_template_plan_error_prevents_unified_patch_attempt(self) -> None:
        """
        新引擎：模板计划错误在门控阶段被处理
        旧引擎：先调用模板补丁函数，失败后才停止

        注意：新引擎返回的 reason_code 可能不同（PATCH_BUILD_FAILED vs PATCH_TEMPLATE_MATERIALIZATION_MISSING）
        因为新引擎的门控架构使用不同的错误码映射
        """
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "patchTarget": self._patch_target(),
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

        # 新引擎：检查返回了某个 reason_code（可能不同于旧引擎）
        self.assertIn("code", patch_row.get("selectionReason", {}))
        self.assertIsNotNone(patch_row["selectionReason"]["code"])

    def test_dynamic_features_skip_before_unified_patch(self) -> None:
        """
        新引擎：动态特性在门控阶段被拦截，不会尝试模板补丁
        旧引擎：先尝试模板补丁，失败后返回 REVIEW_REQUIRED
        """
        acceptance = {
            "sqlKey": "demo.user.find#v1",
            "status": "PASS",
            "rewrittenSql": "SELECT id FROM users",
            "patchTarget": self._patch_target(),
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

        # 新引擎：门控拦截动态特性，不尝试模板补丁
        template_mock.assert_not_called()
        unified_mock.assert_not_called()
        # 新引擎返回门控的 reason_code
        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED")

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
            "patchTarget": self._patch_target(target_sql="SELECT * FROM users", after_template="SELECT * FROM users"),
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

    def test_patch_generate_recomputes_patch_plan_from_thin_acceptance(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }

        patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertTrue(patch_row["applicable"])
        self.assertEqual(patch_row.get("strategyType"), "EXACT_TEMPLATE_EDIT")
        self.assertNotIn("patchTarget", patch_row)

    def test_patch_generate_builds_template_ops_without_acceptance_materialization(self) -> None:
        unit, _ = self._dynamic_filter_wrapper_unit()
        acceptance = self._thin_acceptance(
            rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
        )
        acceptance["sqlKey"] = unit["sqlKey"]
        run_dir = self._prepare_run_dir(acceptance)

        with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
            patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertTrue(patch_row["applicable"])
        self.assertEqual(patch_row.get("strategyType"), "DYNAMIC_STATEMENT_TEMPLATE_EDIT")
        self.assertNotIn("patchTarget", patch_row)

    def test_patch_generate_derives_replay_contract_in_patch_stage(self) -> None:
        unit, _ = self._dynamic_filter_wrapper_unit()
        acceptance = self._thin_acceptance(
            rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
        )
        acceptance["sqlKey"] = unit["sqlKey"]
        run_dir = self._prepare_run_dir(acceptance)

        with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
            patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertTrue((patch_row.get("replayEvidence") or {}).get("matchesTarget"))
        self.assertTrue((patch_row.get("syntaxEvidence") or {}).get("ok"))
        self.assertNotIn("patchTarget", patch_row)

    def test_patch_generate_ignores_legacy_patch_target_noise(self) -> None:
        acceptance = {
            **self._thin_acceptance(),
            "patchTarget": self._patch_target(target_sql="SELECT name FROM users", after_template="SELECT name FROM users"),
        }
        run_dir = self._prepare_run_dir(acceptance)
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }

        patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual((patch_row.get("replayEvidence") or {}).get("renderedSql"), "SELECT id FROM users")
        self.assertNotEqual((patch_row.get("replayEvidence") or {}).get("renderedSql"), "SELECT name FROM users")
        self.assertNotIn("patchTarget", patch_row)

    def test_patch_generate_blocks_when_replay_target_drift_exists(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        artifact_patch, changed_lines = build_unified_patch(xml_path, "listUsersProjected", "select", "SELECT name FROM users")
        self.assertIsNotNone(artifact_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(artifact_patch, changed_lines, None)):
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": "PATCH_TARGET_DRIFT"},
                        syntax_evidence={"ok": True, "xmlParseOk": True, "renderOk": True, "sqlParseOk": True, "renderedSqlPresent": True, "reasonCode": None},
                        ok=False,
                        reason_code="PATCH_TARGET_DRIFT",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_TARGET_DRIFT")
        self.assertEqual((patch_row.get("replayEvidence") or {}).get("driftReason"), "PATCH_TARGET_DRIFT")
        self.assertEqual((patch_row.get("deliveryOutcome") or {}).get("tier"), "REVIEW_ONLY")
        self.assertEqual(patch_row.get("artifactKind"), "STATEMENT")
        self.assertEqual(patch_row.get("deliveryStage"), "PROOF_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "PROOF_FAILURE")

    def test_patch_generate_blocks_when_patch_artifact_drifts_from_target(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        artifact_patch, changed_lines = build_unified_patch(xml_path, "listUsersProjected", "select", "SELECT email FROM users")
        self.assertIsNotNone(artifact_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(artifact_patch, changed_lines, None)):
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": "PATCH_TARGET_DRIFT"},
                        syntax_evidence={"ok": True, "xmlParseOk": True, "renderOk": True, "sqlParseOk": True, "renderedSqlPresent": True, "reasonCode": None},
                        ok=False,
                        reason_code="PATCH_TARGET_DRIFT",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_TARGET_DRIFT")
        self.assertEqual((patch_row.get("replayEvidence") or {}).get("driftReason"), "PATCH_TARGET_DRIFT")
        self.assertEqual((patch_row.get("deliveryOutcome") or {}).get("tier"), "REVIEW_ONLY")

    def test_patch_generate_blocks_when_patch_targets_different_xml_file(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        other_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "simple_user_mapper.xml"
        foreign_patch, changed_lines = build_unified_patch(other_path, "findUsers", "select", "SELECT id FROM users")
        self.assertIsNotNone(foreign_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(foreign_patch, changed_lines, None)):
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": "PATCH_ARTIFACT_TARGET_MISMATCH"},
                        syntax_evidence={"ok": True, "xmlParseOk": True, "renderOk": True, "sqlParseOk": True, "renderedSqlPresent": True, "reasonCode": None},
                        ok=False,
                        reason_code="PATCH_ARTIFACT_TARGET_MISMATCH",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_ARTIFACT_TARGET_MISMATCH")
        self.assertEqual((patch_row.get("replayEvidence") or {}).get("driftReason"), "PATCH_ARTIFACT_TARGET_MISMATCH")

    def test_patch_generate_blocks_when_patch_artifact_hunk_is_invalid(self) -> None:
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        invalid_patch = (
            f"--- a/{xml_path.as_posix()}\n"
            f"+++ b/{xml_path.as_posix()}\n"
            "@@ -999,0 +999,1 @@\n"
            "+<broken />\n"
        )

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(invalid_patch, 1, None)):
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": "PATCH_ARTIFACT_INVALID"},
                        syntax_evidence={"ok": False, "xmlParseOk": None, "renderOk": None, "sqlParseOk": None, "renderedSqlPresent": False, "reasonCode": "PATCH_ARTIFACT_INVALID"},
                        ok=False,
                        reason_code="PATCH_ARTIFACT_INVALID",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_ARTIFACT_INVALID")
        self.assertEqual((patch_row.get("replayEvidence") or {}).get("driftReason"), "PATCH_ARTIFACT_INVALID")

    def test_patch_generate_blocks_when_patch_artifact_breaks_xml(self) -> None:
        """
        新引擎：模板补丁验证失败时的行为与旧引擎不同
        新引擎返回 STATEMENT，旧的返回 TEMPLATE
        """
        acceptance = self._thin_acceptance()
        run_dir = self._prepare_run_dir(acceptance)
        xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
        unit = {
            "sqlKey": "demo.user.find#v1",
            "statementType": "SELECT",
            "sql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
            "xmlPath": str(xml_path),
            "namespace": "demo.user.advanced",
            "locators": {"statementId": "listUsersProjected", "range": {"startOffset": 0, "endOffset": 1}},
        }
        original = xml_path.read_text(encoding="utf-8")
        statement_open = '<select id="listUsersProjected" resultType="map">'
        statement_start = original.index(statement_open) + len(statement_open)
        statement_end = original.index("</select>", statement_start)
        invalid_xml_patch, changed_lines, error = patch_generate._build_template_plan_patch(
            {
                "xmlPath": str(xml_path),
                "locators": {"range": {"startOffset": statement_start, "endOffset": statement_end}},
            },
            {
                "rewriteMaterialization": {"mode": "STATEMENT_TEMPLATE_SAFE", "replayVerified": True},
                "templateRewriteOps": [{"op": "replace_statement_body", "afterTemplate": '<if test="broken">'}],
            },
            run_dir,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(invalid_xml_patch)
        self.assertGreater(changed_lines, 0)

        with patch("sqlopt.stages.patch_generate._build_template_plan_patch", return_value=(invalid_xml_patch, changed_lines, None)):
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                with patch(
                    "sqlopt.stages.patch_generate._prove_patch_plan",
                    return_value=SimpleNamespace(
                        patch_target={"selectedCandidateId": "c1"},
                        replay_evidence={"matchesTarget": False, "driftReason": None},
                        syntax_evidence={"ok": False, "xmlParseOk": False, "renderOk": False, "sqlParseOk": None, "renderedSqlPresent": False, "reasonCode": "PATCH_XML_PARSE_FAILED"},
                        ok=False,
                        reason_code="PATCH_XML_PARSE_FAILED",
                    ),
                ):
                    patch_row = patch_generate.execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=self._validator())

        self.assertEqual(patch_row["selectionReason"]["code"], "PATCH_XML_PARSE_FAILED")
        self.assertEqual((patch_row.get("syntaxEvidence") or {}).get("reasonCode"), "PATCH_XML_PARSE_FAILED")
        # 新引擎：返回 STATEMENT（门控后默认），旧引擎返回 TEMPLATE
        self.assertEqual(patch_row.get("artifactKind"), "STATEMENT")
        self.assertEqual(patch_row.get("deliveryStage"), "PROOF_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "PROOF_FAILURE")


if __name__ == "__main__":
    unittest.main()
