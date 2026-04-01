from __future__ import annotations

from dataclasses import replace
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch

from sqlopt.contracts import ContractValidator
from sqlopt.patch_families.registry import lookup_patch_family_spec
from sqlopt.stages.patch_verification import append_patch_verification
from sqlopt.verification.writer import read_verification_ledger

ROOT = Path(__file__).resolve().parents[2]


def _read_ledger(run_dir: Path) -> list[dict]:
    return read_verification_ledger(run_dir)


class PatchVerificationTest(unittest.TestCase):
    def _validator(self) -> ContractValidator:
        return ContractValidator(ROOT)

    def _append_patch_verification(self, **kwargs: object) -> None:
        patch = kwargs.get("patch")
        acceptance = kwargs.get("acceptance")
        proof_patch_target = kwargs.pop("proof_patch_target", None)
        if proof_patch_target is None and isinstance(patch, dict):
            patch_target = patch.get("patchTarget")
            if isinstance(patch_target, dict):
                proof_patch_target = patch_target
        if proof_patch_target is None and isinstance(acceptance, dict):
            patch_target = acceptance.get("patchTarget")
            if isinstance(patch_target, dict):
                proof_patch_target = patch_target
        append_patch_verification(proof_patch_target=proof_patch_target, **kwargs)

    def _patch_target(self, *, family: str = "STATIC_STATEMENT_REWRITE") -> dict:
        target_sql = "SELECT id FROM users"
        return {
            "sqlKey": "demo.user.find#v1",
            "selectedCandidateId": "c1",
            "targetSql": target_sql,
            "targetSqlNormalized": target_sql,
            "targetSqlFingerprint": "demo-fingerprint",
            "semanticGateStatus": "PASS",
            "semanticGateConfidence": "HIGH",
            "selectedPatchStrategy": {"strategyType": "EXACT_TEMPLATE_EDIT"},
            "family": family,
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
                    "dialectSyntaxCheckRequired": False,
                },
            },
            "templateRewriteOps": [{"op": "replace_statement_body", "afterTemplate": target_sql}],
            "replayContract": {
                "replayMode": "STATEMENT_TEMPLATE_SAFE",
                "requiredTemplateOps": ["replace_statement_body"],
                "expectedRenderedSql": target_sql,
                "expectedRenderedSqlNormalized": target_sql,
                "expectedFingerprint": {"kind": "normalized_sql", "value": target_sql},
                "requiredAnchors": [],
                "requiredIncludes": [],
                "requiredPlaceholderShape": [],
                "dialectSyntaxCheckRequired": False,
            },
            "evidenceRefs": [],
        }

    def test_applicable_patch_is_recorded_as_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_ok_") as td:
            run_dir = Path(td)
            proof_target = self._patch_target()
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS"}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                proof_patch_target=proof_target,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["phase"], "patch_generate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SELECTED_SINGLE_PASS")

    def test_patch_verification_ignores_acceptance_patch_target_noise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_ignore_acceptance_noise_") as td:
            run_dir = Path(td)
            proof_target = self._patch_target()
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {
                "status": "PASS",
                "patchTarget": {
                    **self._patch_target(family="DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
                    "rewriteMaterialization": {"mode": "STATEMENT_TEMPLATE_SAFE", "replayVerified": False},
                },
            }
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                proof_patch_target=proof_target,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SELECTED_SINGLE_PASS")

    def test_template_ops_without_required_replay_do_not_hard_gate_verdict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_unverified_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE", "message": "needs rewrite"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "patchTarget": {
                    **self._patch_target(),
                    "rewriteMaterialization": {"mode": "STATEMENT_TEMPLATE_SAFE", "replayVerified": False},
                },
            }
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE")
        template_check = next(check for check in rows[0]["checks"] if check["name"] == "template_replay_verified")
        self.assertEqual(template_check["severity"], "info")
        self.assertFalse(template_check["ok"])

    def test_patch_verification_marks_replay_mismatch_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_replay_mismatch_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_TARGET_DRIFT", "message": "replay drift"},
                "applicable": False,
                "patchFiles": [],
                "patchTarget": {"family": "STATIC_STATEMENT_REWRITE"},
                "replayEvidence": {"matchesTarget": False, "driftReason": "PATCH_TARGET_DRIFT"},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": {"family": "STATIC_STATEMENT_REWRITE"}}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_TARGET_DRIFT")
        failed_checks = {check["name"]: check for check in rows[0]["checks"] if not check["ok"]}
        self.assertIn("replay_matches_target", failed_checks)

    def test_dynamic_family_if_replay_drift_remains_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_dynamic_if_drift_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_DYNAMIC_IF_TEST_DRIFT", "message": "dynamic if test drift"},
                "applicable": False,
                "patchFiles": [],
                "patchTarget": self._patch_target(family="DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
                "replayEvidence": {"matchesTarget": False, "driftReason": "PATCH_DYNAMIC_IF_TEST_DRIFT"},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": self._patch_target(family="DYNAMIC_FILTER_SELECT_LIST_CLEANUP")}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_DYNAMIC_IF_TEST_DRIFT")
        failed_checks = {check["name"]: check for check in rows[0]["checks"] if not check["ok"]}
        self.assertIn("replay_matches_target", failed_checks)

    def test_semantic_gate_block_is_recorded_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_semantic_gate_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS", "message": "blocked by semantic gate"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "semanticEquivalence": {"status": "UNCERTAIN"},
            }
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="UNCERTAIN",
                semantic_gate_confidence="LOW",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS")

    def test_semantic_low_confidence_block_is_recorded_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_semantic_confidence_") as td:
            run_dir = Path(td)
            patch = {
                "selectionReason": {"code": "PATCH_SEMANTIC_CONFIDENCE_LOW", "message": "blocked by low confidence"},
                "applicable": None,
                "patchFiles": [],
            }
            acceptance = {
                "status": "PASS",
                "semanticEquivalence": {"status": "PASS", "confidence": "LOW"},
            }
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="LOW",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_SEMANTIC_CONFIDENCE_LOW")

    def test_patch_verification_uses_registered_sql_parse_requirement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_registered_policy_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
            assert spec is not None
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": None,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": None,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch(
                "sqlopt.stages.patch_verification.lookup_patch_family_spec",
                return_value=replace(
                    spec,
                    verification=replace(spec.verification, require_sql_parse=False),
                ),
            ):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_verification_keeps_raw_aggregate_syntax_failure_observational(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_aggregate_syntax_failure_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": False,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        syntax_check = next(check for check in rows[0]["checks"] if check["name"] == "syntax_ok")
        self.assertEqual(syntax_check["severity"], "info")
        self.assertFalse(syntax_check["ok"])

    def test_patch_verification_keeps_disabled_sql_parse_failure_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_optional_sql_parse_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
            assert spec is not None
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": False,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch(
                "sqlopt.stages.patch_verification.lookup_patch_family_spec",
                return_value=replace(
                    spec,
                    verification=replace(spec.verification, require_sql_parse=False),
                ),
            ):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_verification_keeps_disabled_sql_parse_aggregate_failure_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_optional_sql_parse_aggregate_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
            assert spec is not None
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": False,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": False,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch(
                "sqlopt.stages.patch_verification.lookup_patch_family_spec",
                return_value=replace(
                    spec,
                    verification=replace(spec.verification, require_sql_parse=False),
                ),
            ):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_verification_keeps_missing_sql_parse_subcheck_non_blocking_when_sql_parse_not_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_optional_sql_parse_missing_subcheck_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
            assert spec is not None
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": False,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch(
                "sqlopt.stages.patch_verification.lookup_patch_family_spec",
                return_value=replace(
                    spec,
                    verification=replace(spec.verification, require_sql_parse=False),
                ),
            ):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "VERIFIED")
        sql_check = next(check for check in rows[0]["checks"] if check["name"] == "sql_parse_ok")
        self.assertEqual(sql_check["severity"], "info")
        # None values are now removed from compact output
        self.assertIsNone(rows[0]["inputs"].get("sql_parse_ok"))
        self.assertIsNone(rows[0]["verdict"].get("sql_parse_ok"))

    def test_patch_verification_marks_missing_required_sql_parse_evidence_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_missing_required_sql_parse_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": False,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_DECISION_EVIDENCE_INCOMPLETE")
        sql_check = next(check for check in rows[0]["checks"] if check["name"] == "sql_parse_ok")
        self.assertEqual(sql_check["reason_code"], "PATCH_DECISION_EVIDENCE_INCOMPLETE")
        # None values are now removed from compact output
        self.assertIsNone(rows[0]["inputs"].get("sql_parse_ok"))
        self.assertIsNone(rows[0]["verdict"].get("sql_parse_ok"))

    def test_patch_verification_marks_missing_registered_family_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_missing_family_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="UNREGISTERED_TEST_FAMILY")
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch("sqlopt.stages.patch_verification.lookup_patch_family_spec", return_value=None):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_FAMILY_SPEC_MISSING")

    def test_patch_verification_prioritizes_missing_family_over_replay_and_syntax_failures(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_missing_family_priority_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="UNREGISTERED_TEST_FAMILY")
            patch = {
                "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "selected"},
                "applicable": True,
                "patchFiles": [str(run_dir / "pipeline" / "patch_generate" / "files" / "demo.patch")],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": False, "driftReason": "PATCH_TARGET_DRIFT"},
                "syntaxEvidence": {
                    "ok": False,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": False,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            with mock_patch("sqlopt.stages.patch_verification.lookup_patch_family_spec", return_value=None):
                self._append_patch_verification(
                    run_dir=run_dir,
                    validator=self._validator(),
                    patch=patch,
                    acceptance=acceptance,
                    status="PASS",
                    semantic_gate_status="PASS",
                    semantic_gate_confidence="HIGH",
                    sql_key="demo.user.find#v1",
                    statement_key="demo.user.find",
                    same_statement=[{"sqlKey": "demo.user.find#v1"}],
                    pass_rows=[{"sqlKey": "demo.user.find#v1"}],
                )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_FAMILY_SPEC_MISSING")

    def test_patch_verification_marks_required_apply_check_failure_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_verification_apply_required_") as td:
            run_dir = Path(td)
            patch_target = self._patch_target(family="STATIC_INCLUDE_WRAPPER_COLLAPSE")
            patch = {
                "selectionReason": {"code": "PATCH_NOT_APPLICABLE", "message": "apply check failed"},
                "applicable": False,
                "patchFiles": [],
                "patchTarget": patch_target,
                "replayEvidence": {"matchesTarget": True, "driftReason": None},
                "syntaxEvidence": {
                    "ok": True,
                    "xmlParseOk": True,
                    "renderOk": True,
                    "sqlParseOk": True,
                    "renderedSqlPresent": True,
                },
            }
            acceptance = {"status": "PASS", "patchTarget": patch_target}
            self._append_patch_verification(
                run_dir=run_dir,
                validator=self._validator(),
                patch=patch,
                acceptance=acceptance,
                status="PASS",
                semantic_gate_status="PASS",
                semantic_gate_confidence="HIGH",
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                same_statement=[{"sqlKey": "demo.user.find#v1"}],
                pass_rows=[{"sqlKey": "demo.user.find#v1"}],
            )
            rows = _read_ledger(run_dir)

        self.assertEqual(rows[0]["status"], "UNVERIFIED")
        self.assertEqual(rows[0]["reason_code"], "PATCH_NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
