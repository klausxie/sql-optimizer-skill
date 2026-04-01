from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.platforms.sql.models import ValidationResult
from sqlopt.stages import optimize, patch_generate, scan, validate

ROOT = Path(__file__).resolve().parents[2]


def _sql_unit() -> dict:
    return {
        "sqlKey": "demo.user.listUsers#v1",
        "xmlPath": "src/main/resources/demo_mapper.xml",
        "namespace": "demo.user",
        "statementId": "listUsers",
        "statementType": "select",
        "variantId": "v1",
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
                "sqlKey": "demo.user.listUsers#v1",
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
                "sqlKey": "demo.user.listUsers#v1",
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
                "sqlKey": "demo.user.listUsers#v1",
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
                "sqlKey": "demo.user.listUsers#v1",
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
            sql_unit["sqlKey"] = "demo.user.cte#v1"
            sql_unit["sql"] = "WITH recent_users AS (SELECT id, created_at FROM users) SELECT id, created_at FROM recent_users ORDER BY created_at DESC"
            proposal = {
                "sqlKey": "demo.user.cte#v1",
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
            diagnostics_path = run_dir / "sql" / "demo_user_cte_v1" / "candidate_generation_diagnostics.json"
            self.assertTrue(diagnostics_path.exists())
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnostics["recoveryStrategy"], "INLINE_SIMPLE_CTE_RECOVERED")

    def test_validate_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_") as td:
            run_dir = Path(td)
            result = ValidationResult(
                sql_key="demo.user.listUsers#v1",
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

        self.assertEqual(rows[0]["phase"], "validate")
        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_patch_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            acceptance = {
                "sqlKey": "demo.user.listUsers#v1",
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
            xml_path = ROOT / "tests" / "fixtures" / "project" / "src" / "main" / "resources" / "com" / "example" / "mapper" / "user" / "advanced_user_mapper.xml"
            xml_text = xml_path.read_text(encoding="utf-8")
            statement_open = '<select id="listUsersProjected" resultType="map">'
            statement_start = xml_text.index(statement_open) + len(statement_open)
            statement_end = xml_text.index("</select>", statement_start)
            rewritten_sql = "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC"
            acceptance = {
                "sqlKey": "demo.user.advanced.listUsersProjected#v1",
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
                        "sqlKey": "demo.user.advanced.listUsersProjected#v1",
                        "xmlPath": str(xml_path),
                        "namespace": "demo.user.advanced",
                        "statementId": "listUsersProjected",
                        "statementType": "select",
                        "variantId": "v1",
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
