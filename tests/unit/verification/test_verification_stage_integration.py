from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.platforms.sql.models import ValidationResult
from sqlopt.stages import optimize, patch_generate, scan, validate

ROOT = Path(__file__).resolve().parents[3]
ADVANCED_USER_MAPPER = (
    ROOT
    / "tests"
    / "fixtures"
    / "projects"
    / "sample_project"
    / "src"
    / "main"
    / "resources"
    / "com"
    / "example"
    / "mapper"
    / "user"
    / "advanced_user_mapper.xml"
)


def _sql_unit() -> dict:
    return {
        "sqlKey": "demo.user.listUsers",
        "statementKey": "demo.user.listUsers",
        "xmlPath": "src/main/resources/demo_mapper.xml",
        "namespace": "demo.user",
        "statementId": "listUsers",
        "statementType": "select",
        "sql": "SELECT id FROM users WHERE id = #{id}",
        "templateSql": "SELECT id FROM users WHERE id = #{id}",
        "parameterMappings": [],
        "paramExample": {"id": 1},
        "locators": {"statementId": "listUsers", "range": {"startOffset": 1, "endOffset": 10}},
        "riskFlags": [],
        "dynamicFeatures": [],
    }


class VerificationStageIntegrationTest(unittest.TestCase):
    def _validator(self) -> ContractValidator:
        return ContractValidator(ROOT)

    def _ledger_rows(self, run_dir: Path) -> list[dict]:
        rows: list[dict] = []
        for rel in ("artifacts/scan.jsonl", "artifacts/proposals.jsonl", "artifacts/acceptance.jsonl", "artifacts/patches.jsonl"):
            path = run_dir / rel
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                verification = payload.get("verification")
                if isinstance(verification, dict):
                    rows.append(verification)
        return rows

    def test_scan_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_scan_") as td:
            run_dir = Path(td)
            config = {
                "project": {"root_path": str(run_dir)},
                "scan": {"mapper_globs": [], "enable_fragment_catalog": False},
                "db": {"platform": "postgresql"},
            }
            with patch("sqlopt.stages.scan.run_scan", return_value=([_sql_unit()], [])):
                units = scan.execute(config, run_dir, self._validator())
                rows = self._ledger_rows(run_dir)

        self.assertEqual(len(units), 1)
        self.assertEqual(rows[0]["phase"], "scan")
        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_optimize_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_") as td:
            run_dir = Path(td)
            proposal = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "issues": [{"code": "SEQ_SCAN"}],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [{"strategy": "index"}],
                "verdict": "ACTIONABLE",
                "actionability": {"score": 85, "tier": "HIGH", "autoPatchLikelihood": "HIGH", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": 0,
            }
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch(
                    "sqlopt.stages.optimize.generate_llm_candidates",
                    return_value=([{"candidateId": "c1", "rewrittenSql": "SELECT id FROM users WHERE id = ?"}], {"executor": "llm"}),
                ):
                    optimize.execute_one(_sql_unit(), run_dir, self._validator(), config={"llm": {}, "project": {}})
                    rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "optimize")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["inputs"]["actionability_tier"], "HIGH")
        self.assertEqual(rows[0]["inputs"]["actionability_score"], 85)

    def test_optimize_stage_marks_db_explain_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_") as td:
            run_dir = Path(td)
            proposal = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "issues": [{"code": "SEQ_SCAN"}],
                "dbEvidenceSummary": {"explainError": "You have an error in your SQL syntax near ILIKE"},
                "planSummary": {"summary": "EXPLAIN failed"},
                "suggestions": [{"strategy": "index"}],
                "verdict": "ACTIONABLE",
                "actionability": {"score": 85, "tier": "HIGH", "autoPatchLikelihood": "HIGH", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": 0,
            }
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch(
                    "sqlopt.stages.optimize.generate_llm_candidates",
                    return_value=([], {"executor": "heuristic"}),
                ):
                    optimize.execute_one(_sql_unit(), run_dir, self._validator(), config={"llm": {}, "project": {}})
                    rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "optimize")
        self.assertEqual(rows[0]["status"], "PARTIAL")
        self.assertEqual(rows[0]["reason_code"], "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR")
        check_codes = {check.get("reason_code") for check in rows[0]["checks"]}
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", check_codes)

    def test_optimize_stage_persists_trace_even_when_llm_candidates_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_trace_empty_") as td:
            run_dir = Path(td)
            proposal = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "issues": [{"code": "SEQ_SCAN"}],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [{"strategy": "index"}],
                "verdict": "ACTIONABLE",
                "actionability": {"score": 85, "tier": "HIGH", "autoPatchLikelihood": "HIGH", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": 0,
            }
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch(
                    "sqlopt.stages.optimize.generate_llm_candidates",
                    return_value=([], {"executor": "opencode_run", "provider": "opencode_run"}),
                ):
                    optimize.execute_one(
                        _sql_unit(),
                        run_dir,
                        self._validator(),
                        config={"llm": {"enabled": True, "provider": "opencode_run"}, "project": {}},
                    )

            proposal_row = json.loads((run_dir / "artifacts" / "proposals.jsonl").read_text(encoding="utf-8").splitlines()[0])
            trace_ref = (proposal_row.get("llmTraceRefs") or [None])[0]
            self.assertTrue(trace_ref)
            trace_path = run_dir / str(trace_ref)
            self.assertTrue(trace_path.exists())
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace.get("executor"), "opencode_run")

    def test_optimize_stage_persists_skip_trace_for_dollar_substitution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_trace_skip_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sql"] = "SELECT * FROM users WHERE id = ${id}"
            proposal = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "issues": [{"code": "DOLLAR_SUBSTITUTION"}],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [],
                "verdict": "NOOP",
                "actionability": {"score": 10, "tier": "LOW", "autoPatchLikelihood": "LOW", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": None,
            }
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                optimize.execute_one(sql_unit, run_dir, self._validator(), config={"llm": {"enabled": True, "provider": "opencode_run"}, "project": {}})

            proposal_row = json.loads((run_dir / "artifacts" / "proposals.jsonl").read_text(encoding="utf-8").splitlines()[0])
            trace_ref = (proposal_row.get("llmTraceRefs") or [None])[0]
            self.assertTrue(trace_ref)
            trace_path = run_dir / str(trace_ref)
            self.assertTrue(trace_path.exists())
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace.get("degrade_reason"), "RISKY_DOLLAR_SUBSTITUTION")

    def test_optimize_stage_recovers_empty_candidates_for_safe_cte(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_recover_empty_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.cte"
            sql_unit["statementKey"] = "demo.user.cte"
            sql_unit["sql"] = "WITH recent_users AS (SELECT id, created_at FROM users) SELECT id, created_at FROM recent_users ORDER BY created_at DESC"
            proposal = {
                "sqlKey": "demo.user.cte",
                "statementKey": "demo.user.cte",
                "issues": [],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [],
                "verdict": "NOOP",
                "actionability": {"score": 40, "tier": "LOW", "autoPatchLikelihood": "LOW", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": None,
            }
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch(
                    "sqlopt.stages.optimize.generate_llm_candidates",
                    return_value=([], {"executor": "opencode_run", "provider": "opencode_run"}),
                ):
                    optimize.execute_one(sql_unit, run_dir, self._validator(), config={"llm": {"enabled": True, "provider": "opencode_run"}, "project": {}})

            proposal_row = json.loads((run_dir / "artifacts" / "proposals.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(proposal_row["llmCandidates"][0]["rewriteStrategy"], "INLINE_SIMPLE_CTE_RECOVERED")
            self.assertEqual(proposal_row["candidateGenerationDiagnostics"]["degradationKind"], "EMPTY_CANDIDATES")
            self.assertTrue(proposal_row["candidateGenerationDiagnostics"]["recoverySucceeded"])
            diagnostics_path = run_dir / "sql" / "demo_user_cte" / "candidate_generation_diagnostics.json"
            self.assertTrue(diagnostics_path.exists())
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["recoveryStrategy"], "INLINE_SIMPLE_CTE_RECOVERED")

    def test_validate_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_") as td:
            run_dir = Path(td)
            result = ValidationResult(
                sql_key="demo.user.listUsers",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="heuristic",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id FROM users WHERE id = ?",
                selected_candidate_id="c1",
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "heuristic", "selectedCandidateId": "c1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(_sql_unit(), {}, run_dir, self._validator(), db_reachable=False, config={})
                rows = self._ledger_rows(run_dir)
                convergence_rows = [
                    json.loads(line)
                    for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]

        self.assertEqual(rows[0]["phase"], "validate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["statementKey"], "demo.user.listUsers")
        self.assertIn(convergence_rows[0]["convergenceDecision"], {"AUTO_PATCHABLE", "MANUAL_REVIEW", "NOT_PATCHABLE"})

    def test_validate_convergence_infers_if_guarded_shape_from_sql_unit_when_rewrite_facts_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_shape_infer_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.listUsersDynamic"
            sql_unit["statementKey"] = "demo.user.listUsersDynamic"
            sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
            sql_unit["templateSql"] = "SELECT id FROM users <where><if test=\"status != null\"> AND status = #{status}</if></where>"
            result = ValidationResult(
                sql_key="demo.user.listUsersDynamic",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="heuristic",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id FROM users WHERE status = ?",
                selected_candidate_id="c1",
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "heuristic", "selectedCandidateId": "c1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, {}, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")

    def test_validate_convergence_labels_choose_filter_statement_but_keeps_it_manual_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_shape_choose_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.listUsersChoose"
            sql_unit["statementKey"] = "demo.user.listUsersChoose"
            sql_unit["dynamicFeatures"] = ["WHERE", "CHOOSE"]
            sql_unit["templateSql"] = (
                "SELECT id FROM users <where><choose>"
                "<when test=\"status != null\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where>"
            )
            result = ValidationResult(
                sql_key="demo.user.listUsersChoose",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="heuristic",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id FROM users WHERE status = ?",
                selected_candidate_id="c1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "heuristic", "selectedCandidateId": "c1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, {}, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")

    def test_validate_convergence_allows_choose_filter_select_cleanup_when_patch_family_is_supported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_shape_choose_select_cleanup_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.listUsersChooseAliases"
            sql_unit["statementKey"] = "demo.user.listUsersChooseAliases"
            sql_unit["dynamicFeatures"] = ["WHERE", "CHOOSE"]
            sql_unit["templateSql"] = (
                "SELECT id AS id, name AS name FROM users <where><choose>"
                "<when test=\"status != null\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where>"
            )
            proposal = {
                "sqlKey": "demo.user.listUsersChooseAliases",
                "statementKey": "demo.user.listUsersChooseAliases",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
                        "rewrittenSql": "SELECT id, name FROM users WHERE (status = #{status} OR status != 'DELETED')",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
                },
            }
            result = ValidationResult(
                sql_key="demo.user.listUsersChooseAliases",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name FROM users WHERE (status = #{status} OR status != 'DELETED')",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "DYNAMIC_FILTER_SELECT_LIST_CLEANUP")

    def test_validate_convergence_allows_if_guarded_count_wrapper_with_dynamic_count_family(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_count_wrapper_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.countUsersFilteredWrapped"
            sql_unit["statementKey"] = "demo.user.countUsersFilteredWrapped"
            sql_unit["sql"] = "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}"
            sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
            sql_unit["templateSql"] = (
                "SELECT COUNT(1) FROM (SELECT id FROM users <where>"
                "<if test=\"status != null and status != ''\">AND status = #{status}</if>"
                "<if test=\"createdAfter != null\">AND created_at >= #{createdAfter}</if>"
                "</where>) u"
            )
            proposal = {
                "sqlKey": "demo.user.countUsersFilteredWrapped",
                "statementKey": "demo.user.countUsersFilteredWrapped",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "SUBQUERY_REMOVAL",
                        "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.countUsersFilteredWrapped",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_COUNT_WRAPPER")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "DYNAMIC_COUNT_WRAPPER_COLLAPSE")

    def test_validate_convergence_does_not_classify_direct_count_filter_as_count_wrapper(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_count_direct_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.countUsersDirectFiltered"
            sql_unit["statementKey"] = "demo.user.countUsersDirectFiltered"
            sql_unit["sql"] = "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}"
            sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
            sql_unit["templateSql"] = (
                "SELECT COUNT(*) FROM users <where>"
                "<if test=\"status != null and status != ''\">AND status = #{status}</if>"
                "<if test=\"createdAfter != null\">AND created_at >= #{createdAfter}</if>"
                "</where>"
            )
            proposal = {
                "sqlKey": "demo.user.countUsersDirectFiltered",
                "statementKey": "demo.user.countUsersDirectFiltered",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.countUsersDirectFiltered",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                selected_candidate_id=None,
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")

    def test_validate_convergence_allows_static_include_wrapper_with_inline_subquery_family(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_static_include_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.listUsersViaStaticIncludeWrapped"
            sql_unit["statementKey"] = "demo.user.advanced.listUsersViaStaticIncludeWrapped"
            sql_unit["sql"] = (
                "SELECT id, name, email, status, created_at, updated_at FROM ( "
                "SELECT id, name, email, status, created_at, updated_at FROM users "
                ") u ORDER BY created_at DESC"
            )
            sql_unit["dynamicFeatures"] = ["INCLUDE"]
            sql_unit["templateSql"] = (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM ( SELECT <include refid=\"AdvancedUserColumns\" /> FROM users ) u ORDER BY created_at DESC"
            )
            proposal = {
                "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped",
                "statementKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "INLINE_SUBQUERY",
                        "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.listUsersViaStaticIncludeWrapped",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "STATIC_INCLUDE_ONLY")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "STATIC_INCLUDE_WRAPPER_COLLAPSE")

    def test_validate_convergence_reports_no_candidate_for_static_include_without_patch_family(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_static_include_no_candidate_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.listUsersRecentPaged"
            sql_unit["statementKey"] = "demo.user.advanced.listUsersRecentPaged"
            sql_unit["sql"] = "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100"
            sql_unit["dynamicFeatures"] = ["INCLUDE"]
            sql_unit["templateSql"] = (
                "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users ORDER BY created_at DESC LIMIT 100"
            )
            proposal = {
                "sqlKey": "demo.user.advanced.listUsersRecentPaged",
                "statementKey": "demo.user.advanced.listUsersRecentPaged",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.listUsersRecentPaged",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
                selected_candidate_id=None,
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "STATIC_INCLUDE_ONLY")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_SELECTED")

    def test_validate_convergence_labels_union_statement_and_keeps_it_manual_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_union_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.shipment.harness.listShipmentStatusUnion"
            sql_unit["statementKey"] = "demo.shipment.harness.listShipmentStatusUnion"
            sql_unit["sql"] = (
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
            )
            sql_unit["templateSql"] = sql_unit["sql"]
            sql_unit["dynamicFeatures"] = []
            proposal = {
                "sqlKey": sql_unit["sqlKey"],
                "statementKey": sql_unit["statementKey"],
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key=sql_unit["sqlKey"],
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql=sql_unit["sql"],
                selected_candidate_id=None,
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "UNION")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")

    def test_validate_convergence_allows_static_statement_rewrite_for_redundant_subquery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_static_statement_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.listUsersProjected"
            sql_unit["statementKey"] = "demo.user.advanced.listUsersProjected"
            sql_unit["sql"] = (
                "SELECT id, name, email, status, created_at, updated_at FROM ( "
                "SELECT id, name, email, status, created_at, updated_at FROM users "
                ") u ORDER BY created_at DESC"
            )
            sql_unit["dynamicFeatures"] = []
            sql_unit["templateSql"] = (
                "SELECT id, name, email, status, created_at, updated_at FROM ( "
                "SELECT id, name, email, status, created_at, updated_at FROM users "
                ") u ORDER BY created_at DESC"
            )
            proposal = {
                "sqlKey": "demo.user.advanced.listUsersProjected",
                "statementKey": "demo.user.advanced.listUsersProjected",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY",
                        "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.listUsersProjected",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "STATIC_SUBQUERY_WRAPPER")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "STATIC_SUBQUERY_WRAPPER_COLLAPSE")

    def test_validate_convergence_allows_static_alias_projection_cleanup_for_alias_cleanup_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_static_statement_alias_cleanup_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.listUsersProjectedAliases"
            sql_unit["statementKey"] = "demo.user.advanced.listUsersProjectedAliases"
            sql_unit["sql"] = (
                "SELECT id AS id, name AS name, email AS email, status AS status, "
                "created_at AS created_at, updated_at AS updated_at FROM users ORDER BY created_at DESC"
            )
            sql_unit["dynamicFeatures"] = []
            sql_unit["templateSql"] = (
                "SELECT id AS id, name AS name, email AS email, status AS status, "
                "created_at AS created_at, updated_at AS updated_at FROM users ORDER BY created_at DESC"
            )
            proposal = {
                "sqlKey": "demo.user.advanced.listUsersProjectedAliases",
                "statementKey": "demo.user.advanced.listUsersProjectedAliases",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
                        "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.listUsersProjectedAliases",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "STATIC_ALIAS_PROJECTION")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "STATIC_ALIAS_PROJECTION_CLEANUP")

    def test_validate_convergence_allows_static_cte_inline_from_inline_cte_strategy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_static_cte_inline_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.listRecentUsersViaCte"
            sql_unit["statementKey"] = "demo.user.advanced.listRecentUsersViaCte"
            sql_unit["sql"] = (
                "WITH recent_users AS ( SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE created_at >= #{createdAfter} ) "
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM recent_users ORDER BY created_at DESC LIMIT 20"
            )
            sql_unit["dynamicFeatures"] = []
            sql_unit["templateSql"] = sql_unit["sql"]
            proposal = {
                "sqlKey": "demo.user.advanced.listRecentUsersViaCte",
                "statementKey": "demo.user.advanced.listRecentUsersViaCte",
                "llmCandidates": [
                    {
                        "id": "candidate_1",
                        "rewriteStrategy": "INLINE_CTE",
                        "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
                    }
                ],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.listRecentUsersViaCte",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= #{createdAfter} ORDER BY created_at DESC LIMIT 20",
                selected_candidate_id="candidate_1",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["shapeFamily"], "STATIC_STATEMENT")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "STATIC_CTE_INLINE")

    def test_validate_convergence_recovers_patch_family_from_proposal_strategy_when_rewrite_facts_missing(self) -> None:
        cases = (
            ("REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("REMOVE_REDUNDANT_ALIASES", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("REDUNDANT_ALIAS_REMOVAL", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("alias_removal", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("remove-redundant-aliases", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("remove_unnecessary_aliases", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
            ("REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED", "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"),
            ("REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED", "GROUP_BY_FROM_ALIAS_CLEANUP"),
            ("REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED", "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"),
            ("REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED", "DISTINCT_FROM_ALIAS_CLEANUP"),
            ("REMOVE_REDUNDANT_SUBQUERY", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
            ("INLINE_SUBQUERY", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
            ("subquery_unwrap", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
            ("remove_redundant_subquery_wrapper", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
            ("remove-redundant-subquery-wrapper", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
            ("Remove redundant subquery wrapper - outer SELECT selects all columns from inner query without transformation", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
        )
        for rewrite_strategy, expected_family in cases:
            with self.subTest(rewrite_strategy=rewrite_strategy):
                with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_family_recover_") as td:
                    run_dir = Path(td)
                    sql_unit = _sql_unit()
                    sql_unit["sqlKey"] = "demo.user.listUsersDynamic"
                    sql_unit["statementKey"] = "demo.user.listUsersDynamic"
                    sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
                    sql_unit["templateSql"] = "SELECT id FROM users <where><if test=\"status != null\"> AND status = #{status}</if></where>"
                    proposal = {
                        "sqlKey": "demo.user.listUsersDynamic",
                        "statementKey": "demo.user.listUsersDynamic",
                        "llmCandidates": [
                            {
                                "id": "candidate_1",
                                "rewriteStrategy": rewrite_strategy,
                                "rewrittenSql": "SELECT id FROM users WHERE status = ?",
                            }
                        ],
                        "candidateGenerationDiagnostics": {
                            "recoveryStrategy": rewrite_strategy,
                        },
                    }
                    result = ValidationResult(
                        sql_key="demo.user.listUsersDynamic",
                        status="PASS",
                        equivalence={"checked": True},
                        perf_comparison={"checked": True, "reasonCodes": []},
                        security_checks={"dollar_substitution_removed": True},
                        semantic_risk="low",
                        feedback=None,
                        selected_candidate_source="llm",
                        warnings=[],
                        risk_flags=[],
                        rewritten_sql="SELECT id FROM users WHERE status = ?",
                        selected_candidate_id="candidate_1",
                        semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                        decision_layers={
                            "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                            "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                            "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_1"},
                            "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                        },
                    )
                    with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                        validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

                    convergence_rows = [
                        json.loads(line)
                        for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]

                self.assertEqual(len(convergence_rows), 1)
                self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
                self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], expected_family)

    def test_validate_convergence_recovers_patch_family_from_selected_candidate_when_multiple_llm_candidates_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_family_selected_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.listUsersDynamic"
            sql_unit["statementKey"] = "demo.user.listUsersDynamic"
            sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
            sql_unit["templateSql"] = "SELECT id AS id FROM users <where><if test=\"status != null\"> AND status = #{status}</if></where>"
            proposal = {
                "sqlKey": "demo.user.listUsersDynamic",
                "statementKey": "demo.user.listUsersDynamic",
                "llmCandidates": [
                    {
                        "id": "candidate_irrelevant",
                        "rewriteStrategy": "explicit_cast",
                        "rewrittenSql": "SELECT id FROM users WHERE status = CAST(? AS varchar)",
                    },
                    {
                        "id": "candidate_selected",
                        "rewriteStrategy": "remove_redundant_aliases",
                        "rewrittenSql": "SELECT id FROM users WHERE status = ?",
                    },
                ],
                "candidateGenerationDiagnostics": {},
            }
            result = ValidationResult(
                sql_key="demo.user.listUsersDynamic",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id FROM users WHERE status = ?",
                selected_candidate_id="candidate_selected",
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "candidate_selected"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )

            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(convergence_rows[0]["convergenceDecision"], "AUTO_PATCHABLE")
        self.assertEqual(convergence_rows[0]["consensus"]["patchFamily"], "DYNAMIC_FILTER_SELECT_LIST_CLEANUP")

    def test_validate_convergence_uses_specific_reason_when_no_patchable_candidate_is_selected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_no_candidate_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.listUsersDynamic"
            sql_unit["statementKey"] = "demo.user.listUsersDynamic"
            sql_unit["dynamicFeatures"] = ["WHERE", "IF"]
            sql_unit["templateSql"] = "SELECT id FROM users <where><if test=\"status != null\"> AND status = #{status}</if></where>"
            proposal = {
                "sqlKey": "demo.user.listUsersDynamic",
                "statementKey": "demo.user.listUsersDynamic",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "recoveryStrategy": None,
                    "recoverySucceeded": False,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.listUsersDynamic",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id FROM users WHERE status = ?",
                selected_candidate_id=None,
                semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                decision_layers={
                    "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, proposal, run_dir, self._validator(), db_reachable=True, config={})

            convergence_rows = [
                json.loads(line)
                for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(len(convergence_rows), 1)
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_SELECTED")

    def test_patch_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_patch_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            acceptance = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "status": "FAIL",
                "equivalence": {"checked": True},
                "perfComparison": {"checked": True, "reasonCodes": []},
                "securityChecks": {"dollar_substitution_removed": True},
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            patch_generate.execute_one(_sql_unit(), acceptance, run_dir, self._validator())
            rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "patch_generate")
        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_stage_records_replay_and_syntax_verdict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_patch_replay_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            xml_path = ADVANCED_USER_MAPPER
            xml_text = xml_path.read_text(encoding="utf-8")
            statement_open = '<select id="listUsersProjected" resultType="map">'
            statement_start = xml_text.index(statement_open) + len(statement_open)
            statement_end = xml_text.index("</select>", statement_start)
            rewritten_sql = "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC"
            acceptance = {
                "sqlKey": "demo.user.advanced.listUsersProjected",
                "statementKey": "demo.user.advanced.listUsersProjected",
                "status": "PASS",
                "rewrittenSql": rewritten_sql,
                "selectedCandidateId": "c1",
                "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                "equivalence": {"checked": True},
                "perfComparison": {"checked": True, "reasonCodes": []},
                "securityChecks": {"dollar_substitution_removed": True},
            }
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with patch("sqlopt.stages.patch_generate._check_patch_applicable", return_value=(True, None)):
                patch_generate.execute_one(
                    {
                        "sqlKey": "demo.user.advanced.listUsersProjected",
                        "statementKey": "demo.user.advanced.listUsersProjected",
                        "xmlPath": str(xml_path),
                        "namespace": "demo.user.advanced",
                        "statementId": "listUsersProjected",
                        "statementType": "select",
                        "sql": "SELECT id, name, email, status, created_at, updated_at FROM ( SELECT id, name, email, status, created_at, updated_at FROM users ) u ORDER BY created_at DESC",
                        "templateSql": "SELECT id, name, email, status, created_at, updated_at FROM ( SELECT id, name, email, status, created_at, updated_at FROM users ) u ORDER BY created_at DESC",
                        "parameterMappings": [],
                        "paramExample": {},
                        "locators": {
                            "statementId": "listUsersProjected",
                            "range": {"startOffset": statement_start, "endOffset": statement_end},
                        },
                        "riskFlags": [],
                        "dynamicFeatures": [],
                    },
                    acceptance,
                    run_dir,
                    self._validator(),
                )
                rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "patch_generate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertTrue(rows[0]["verdict"]["replay_matches_target"])
        self.assertTrue(rows[0]["verdict"]["syntax_ok"])
