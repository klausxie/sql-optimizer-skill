from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.stages.patch_generate import execute_one

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PROJECT_ROOT = ROOT / "tests" / "fixtures" / "projects" / "sample_project"
SIMPLE_USER_MAPPER = (
    FIXTURE_PROJECT_ROOT
    / "src"
    / "main"
    / "resources"
    / "com"
    / "example"
    / "mapper"
    / "user"
    / "simple_user_mapper.xml"
)


class PatchApplicabilityTest(unittest.TestCase):
    def _base_unit(self) -> dict:
        return {
            "sqlKey": "demo.user.listUsersSorted",
            "statementType": "SELECT",
            "sql": "SELECT * FROM users ORDER BY created_at DESC",
            "xmlPath": str(SIMPLE_USER_MAPPER),
            "locators": {"statementId": "listUsers"},
        }

    def _base_acceptance(self) -> dict:
        return {
            "sqlKey": "demo.user.listUsersSorted",
            "status": "PASS",
            "rewrittenSql": "SELECT id, name FROM users ORDER BY created_at DESC",
            "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
            "equivalence": {},
            "perfComparison": {},
            "securityChecks": {},
            "selectedCandidateId": "c-pass-1",
        }

    def test_patch_marked_applicable_when_git_apply_check_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_applicable_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = self._base_acceptance()
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            patch_row = execute_one(
                run_dir=run_dir,
                sql_unit=self._base_unit(),
                acceptance=acceptance,
                validator=ContractValidator(ROOT),
            )

        self.assertFalse(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_SELECTED_SINGLE_PASS")
        self.assertTrue(patch_row.get("applicable"))
        self.assertIsNone(patch_row.get("applyCheckError"))
        self.assertTrue(patch_row.get("patchFiles"))
        self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "AUTO_PATCH")
        self.assertTrue(patch_row.get("patchability", {}).get("applyCheckPassed"))

    def test_patch_formats_single_line_sql_for_readability(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_format_readable_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                **self._base_acceptance(),
                "rewrittenSql": "SELECT id, name FROM users WHERE deleted = 0 AND status = #{status} ORDER BY created_at DESC",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ):
                patch_row = execute_one(
                    run_dir=run_dir,
                    sql_unit=self._base_unit(),
                    acceptance=acceptance,
                    validator=ContractValidator(ROOT),
                )
                patch_text = Path(patch_row["patchFiles"][0]).read_text(encoding="utf-8")

        self.assertIn("+    FROM users", patch_text)
        self.assertIn("+    AND status = #{status}", patch_text)
        self.assertIn("+    ORDER BY created_at DESC", patch_text)

    def test_patch_apply_check_uses_project_root_from_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_project_root_") as td:
            tmp = Path(td)
            run_dir = tmp / "run"
            project_root = tmp / "project-root"
            run_dir.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = self._base_acceptance()
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ) as run_mock:
                execute_one(
                    run_dir=run_dir,
                    sql_unit=self._base_unit(),
                    acceptance=acceptance,
                    validator=ContractValidator(ROOT),
                    config={"project": {"root_path": str(project_root)}},
                )

        self.assertEqual(run_mock.call_args.kwargs.get("cwd"), project_root.resolve())

    def test_patch_not_created_for_whitespace_only_rewrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_noop_whitespace_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.listUsersSorted",
                "status": "PASS",
                "rewrittenSql": " SELECT  *   FROM   users   ORDER   BY created_at DESC ",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            with patch("sqlopt.stages.patch_generate._build_template_plan_patch") as template_mock:
                with patch("sqlopt.stages.patch_generate._build_unified_patch") as unified_mock:
                    patch_row = execute_one(
                        run_dir=run_dir,
                        sql_unit=self._base_unit(),
                        acceptance=acceptance,
                        validator=ContractValidator(ROOT),
                    )

            template_mock.assert_not_called()
            unified_mock.assert_not_called()
            self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_NO_EFFECTIVE_CHANGE")
            self.assertEqual(patch_row.get("patchFiles"), [])
            patch_file = run_dir / "patches" / "demo.user.listUsersSorted.patch"
            self.assertFalse(patch_file.exists())

    def test_patch_skips_statement_level_include_change_without_fragment_rewrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_include_safe_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded">
    SELECT * FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>""",
                encoding="utf-8",
            )
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findIncluded",
                "status": "PASS",
                "rewrittenSql": "SELECT id, name FROM users WHERE status = #{status}",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.user.findIncluded",
                "statementType": "SELECT",
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "templateSql": 'SELECT * FROM users <include refid="BaseWhere" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeTrace": ["demo.user.BaseWhere"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.BaseWhere", "dynamicFeatures": []}],
                },
                "xmlPath": str(mapper),
                "locators": {"statementId": "findIncluded"},
            }
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ):
                patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

            self.assertTrue(patch_row["diffSummary"].get("skipped", False))
            self.assertEqual(
                patch_row.get("selectionReason", {}).get("code"),
                "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
            )
            self.assertEqual(patch_row.get("patchFiles"), [])
            self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "BLOCKED")
            self.assertEqual(patch_row.get("repairHints", []), [])

    def test_patch_not_applicable_when_git_apply_check_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_not_applicable_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = self._base_acceptance()
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="patch does not apply"),
            ):
                patch_row = execute_one(
                    run_dir=run_dir,
                    sql_unit=self._base_unit(),
                    acceptance=acceptance,
                    validator=ContractValidator(ROOT),
                )

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_NOT_APPLICABLE")
        self.assertFalse(patch_row.get("applicable"))
        self.assertIn("patch does not apply", str(patch_row.get("applyCheckError")))
        self.assertEqual(patch_row.get("patchFiles"), [])
        self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "REVIEW_ONLY")
        self.assertEqual(patch_row.get("artifactKind"), "STATEMENT")
        self.assertEqual(patch_row.get("deliveryStage"), "APPLICABILITY_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "APPLICABILITY_FAILURE")
        self.assertEqual(patch_row.get("repairHints", [])[0].get("actionType"), "GIT_CONFLICT")

    def test_patch_rejects_statement_template_ops_from_validate_without_patch_owned_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_stmt_template_ops_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded">
    SELECT * FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>""",
                encoding="utf-8",
            )
            body = """\n    SELECT * FROM users\n    <include refid="BaseWhere" />\n  """
            start = mapper.read_text(encoding="utf-8").index(body)
            end = start + len(body)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findIncluded",
                "status": "PASS",
                "rewrittenSql": "SELECT id, name FROM users WHERE status = #{status}",
                "rewriteMaterialization": {
                    "mode": "STATEMENT_TEMPLATE_SAFE",
                    "targetType": "STATEMENT",
                    "targetRef": "demo.user.findIncluded",
                    "replayVerified": True,
                },
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "targetRef": "demo.user.findIncluded",
                        "afterTemplate": 'SELECT id, name FROM users <include refid="BaseWhere" />',
                    }
                ],
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(json.dumps(acceptance) + "\n", encoding="utf-8")
            unit = {
                "sqlKey": "demo.user.findIncluded",
                "statementType": "SELECT",
                "namespace": "demo.user",
                "statementId": "findIncluded",
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "dynamicFeatures": ["INCLUDE", "IF"],
                "xmlPath": str(mapper),
                "locators": {"statementId": "findIncluded", "range": {"startOffset": start, "endOffset": end}},
            }
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ):
                patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

            self.assertTrue(patch_row["diffSummary"].get("skipped", False))
            self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_TARGET_CONTRACT_MISSING")
            self.assertEqual(patch_row.get("patchFiles"), [])
            self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "REVIEW_ONLY")

    def test_patch_uses_dynamic_template_specific_reason_when_available(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_dynamic_reason_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.order">
  <select id="findOrdersByNos">
    SELECT * FROM orders
    <where>
      <foreach collection="orderNos" item="orderNo" open="order_no IN (" separator="," close=")">
        #{orderNo}
      </foreach>
    </where>
  </select>
</mapper>""",
                encoding="utf-8",
            )
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.order.findOrdersByNos",
                "status": "PASS",
                "rewrittenSql": "SELECT id, order_no FROM orders WHERE order_no IN (#{orderNo})",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
                "semanticEquivalence": {"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                "dynamicTemplate": {
                    "present": True,
                    "shapeFamily": "FOREACH_IN_PREDICATE",
                    "capabilityTier": "REVIEW_REQUIRED",
                    "patchSurface": "WHERE_CLAUSE",
                    "blockingReason": "FOREACH_INCLUDE_PREDICATE",
                },
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.order.findOrdersByNos",
                "statementType": "SELECT",
                "namespace": "demo.order",
                "statementId": "findOrdersByNos",
                "sql": "SELECT * FROM orders WHERE order_no IN (#{orderNo})",
                "templateSql": (
                    "SELECT * FROM orders <where><foreach collection=\"orderNos\" item=\"orderNo\">"
                    "#{orderNo}</foreach></where>"
                ),
                "dynamicFeatures": ["WHERE", "FOREACH"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "FOREACH"]},
                "xmlPath": str(mapper),
                "locators": {"statementId": "findOrdersByNos"},
            }
            patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(
            patch_row.get("selectionReason", {}).get("code"),
            "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED",
        )
        self.assertEqual(patch_row.get("dynamicTemplateBlockingReason"), "FOREACH_COLLECTION_PREDICATE")

    def test_patch_rejects_fragment_template_ops_from_validate_without_patch_owned_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_fragment_ops_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="BaseWhere">WHERE status = #{status}</sql>
  <select id="findIncluded">
    SELECT * FROM users
    <include refid="BaseWhere" />
  </select>
</mapper>""",
                encoding="utf-8",
            )
            fragment_body = "WHERE status = #{status}"
            start = mapper.read_text(encoding="utf-8").index(fragment_body)
            end = start + len(fragment_body)
            fragment_key = f"{mapper.resolve()}::demo.user.BaseWhere"
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            (run_dir / "artifacts" / "fragments.jsonl").write_text(
                json.dumps(
                    {
                        "fragmentKey": fragment_key,
                        "displayRef": "demo.user.BaseWhere",
                        "xmlPath": str(mapper),
                        "namespace": "demo.user",
                        "fragmentId": "BaseWhere",
                        "templateSql": fragment_body,
                        "dynamicFeatures": [],
                        "includeTrace": [],
                        "dynamicTrace": {"templateFeatures": [], "includeFragments": [], "resolutionDegraded": False},
                        "includeBindings": [],
                        "locators": {
                            "nodeType": "SQL_FRAGMENT",
                            "fragmentId": "BaseWhere",
                            "range": {"startOffset": start, "endOffset": end},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            acceptance = {
                "sqlKey": "demo.user.findIncluded",
                "status": "PASS",
                "rewrittenSql": "SELECT * FROM users WHERE status = #{status} ORDER BY created_at DESC",
                "rewriteMaterialization": {
                    "mode": "FRAGMENT_TEMPLATE_SAFE",
                    "targetType": "SQL_FRAGMENT",
                    "targetRef": fragment_key,
                    "replayVerified": True,
                },
                "templateRewriteOps": [
                    {
                        "op": "replace_fragment_body",
                        "targetRef": fragment_key,
                        "afterTemplate": "WHERE status = #{status} ORDER BY created_at DESC",
                    }
                ],
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(json.dumps(acceptance) + "\n", encoding="utf-8")
            unit = {
                "sqlKey": "demo.user.findIncluded",
                "statementType": "SELECT",
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "dynamicFeatures": ["INCLUDE"],
                "xmlPath": str(mapper),
                "locators": {"statementId": "findIncluded"},
            }
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ):
                patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

            self.assertTrue(patch_row["diffSummary"].get("skipped", False))
            self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_TARGET_CONTRACT_MISSING")
            self.assertEqual(patch_row.get("patchFiles"), [])
            self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "REVIEW_ONLY")

    def test_template_patch_is_blocked_when_duplicate_clause_detected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_dup_clause_") as td:
            run_dir = Path(td)
            mapper = run_dir / "demo_mapper.xml"
            mapper.write_text(
                """<mapper namespace="demo.user">
  <sql id="UserBaseColumns">id, name</sql>
  <select id="listUsers">
    SELECT <include refid="UserBaseColumns" />
    FROM users
  </select>
</mapper>""",
                encoding="utf-8",
            )
            body = """\n    SELECT <include refid="UserBaseColumns" />\n    FROM users\n  """
            start = mapper.read_text(encoding="utf-8").index(body)
            end = start + len(body)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.listUsers",
                "status": "PASS",
                "rewrittenSql": "SELECT id, name FROM users ORDER BY status",
                "rewriteMaterialization": {
                    "mode": "STATEMENT_TEMPLATE_SAFE",
                    "targetType": "STATEMENT",
                    "targetRef": "demo.user.listUsers",
                    "replayVerified": True,
                },
                "templateRewriteOps": [
                    {
                        "op": "replace_statement_body",
                        "targetRef": "demo.user.listUsers",
                        "afterTemplate": 'SELECT <include refid="UserBaseColumns" /> FROM users FROM users ORDER BY status',
                    }
                ],
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(json.dumps(acceptance) + "\n", encoding="utf-8")
            unit = {
                "sqlKey": "demo.user.listUsers",
                "statementType": "SELECT",
                "namespace": "demo.user",
                "statementId": "listUsers",
                "sql": "SELECT id, name FROM users",
                "dynamicFeatures": ["INCLUDE"],
                "xmlPath": str(mapper),
                "locators": {"statementId": "listUsers", "range": {"startOffset": start, "endOffset": end}},
            }
            with patch(
                "sqlopt.stages.patch_generate.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr=""),
            ):
                patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED")
        self.assertEqual(patch_row.get("deliveryOutcome", {}).get("tier"), "REVIEW_ONLY")
        self.assertEqual(patch_row.get("artifactKind"), "TEMPLATE")
        self.assertEqual(patch_row.get("deliveryStage"), "BUILD_FAILED")
        self.assertEqual(patch_row.get("failureClass"), "BUILD_FAILURE")
        self.assertEqual(patch_row.get("repairHints", [])[0].get("actionType"), "MANUAL_PATCH")

    def test_patch_is_skipped_when_placeholder_semantics_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_placeholder_mismatch_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findUsersByStatusRecent",
                "status": "PASS",
                "rewrittenSql": "SELECT id, name, email, status, created_at FROM users WHERE status = ? ORDER BY created_at DESC",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.user.findUsersByStatusRecent",
                "statementType": "SELECT",
                "sql": "SELECT id, name, email, status, created_at FROM users WHERE status = #{status} ORDER BY created_at DESC",
                "xmlPath": str(
                    ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"
                ),
                "locators": {"statementId": "findUsersByStatusRecent"},
            }
            patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(patch_row.get("selectionReason", {}).get("code"), "PATCH_PLACEHOLDER_MISMATCH")
        self.assertEqual(patch_row.get("patchFiles"), [])

    def test_patch_is_skipped_for_dynamic_template_statement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_dynamic_xml_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findByList",
                "status": "PASS",
                "rewrittenSql": "SELECT id FROM users WHERE id IN (#{item.id}, #{item.id})",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.user.findByList",
                "statementType": "SELECT",
                "sql": "SELECT id FROM users WHERE id IN (#{item.id}, #{item.id})",
                "templateSql": 'SELECT id FROM users WHERE id IN <foreach collection="list" item="item">#{item.id}</foreach>',
                "dynamicFeatures": ["FOREACH"],
                "xmlPath": str(
                    ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"
                ),
                "locators": {"statementId": "findByList"},
            }
            patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(
            patch_row.get("selectionReason", {}).get("code"),
            "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED",
        )
        self.assertEqual(patch_row.get("patchFiles"), [])

    def test_patch_is_skipped_for_include_fragment_rewrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_include_fragment_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findIncluded",
                "status": "PASS",
                "rewrittenSql": "SELECT id FROM users WHERE status = #{status}",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.user.findIncluded",
                "statementType": "SELECT",
                "sql": "SELECT id FROM users WHERE status = #{status}",
                "templateSql": 'SELECT id FROM users <include refid="BaseWhere" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeTrace": ["demo.user.BaseWhere"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [{"ref": "demo.user.BaseWhere", "dynamicFeatures": []}],
                },
                "xmlPath": str(
                    ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"
                ),
                "locators": {"statementId": "findIncluded"},
            }
            patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(
            patch_row.get("selectionReason", {}).get("code"),
            "PATCH_BUILD_FAILED",
        )
        self.assertIn("statement not found in mapper", patch_row.get("selectionReason", {}).get("message", ""))

    def test_patch_is_skipped_for_dynamic_include_fragment_rewrite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_dynamic_include_fragment_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            acceptance = {
                "sqlKey": "demo.user.findIncludedDynamic",
                "status": "PASS",
                "rewrittenSql": "SELECT id FROM users WHERE status = #{status}",
                "equivalence": {},
                "perfComparison": {},
                "securityChecks": {},
                "selectedCandidateId": "c-pass-1",
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            unit = {
                "sqlKey": "demo.user.findIncludedDynamic",
                "statementType": "SELECT",
                "sql": "SELECT id FROM users WHERE status = #{status}",
                "templateSql": 'SELECT id FROM users <include refid="BaseWhere" />',
                "dynamicFeatures": ["INCLUDE"],
                "includeTrace": ["demo.user.BaseWhere", "demo.user.NameFilter"],
                "dynamicTrace": {
                    "statementFeatures": ["INCLUDE"],
                    "includeFragments": [
                        {"ref": "demo.user.BaseWhere", "dynamicFeatures": ["IF", "INCLUDE"]},
                        {"ref": "demo.user.NameFilter", "dynamicFeatures": []},
                    ],
                },
                "xmlPath": str(
                    ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "user_mapper.xml"
                ),
                "locators": {"statementId": "findIncludedDynamic"},
            }
            patch_row = execute_one(run_dir=run_dir, sql_unit=unit, acceptance=acceptance, validator=ContractValidator(ROOT))

        self.assertTrue(patch_row["diffSummary"].get("skipped", False))
        self.assertEqual(
            patch_row.get("selectionReason", {}).get("code"),
            "PATCH_BUILD_FAILED",
        )
        self.assertIn("statement not found in mapper", patch_row.get("selectionReason", {}).get("message", ""))


if __name__ == "__main__":
    unittest.main()
