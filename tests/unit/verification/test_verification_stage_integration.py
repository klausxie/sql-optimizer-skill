from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.platforms.sql.llm_cassette import (
    build_optimize_cassette_fingerprint_input,
    fingerprint_optimize_cassette_input,
    optimize_normalized_cassette_path,
    optimize_raw_cassette_path,
)
from sqlopt.platforms.sql.models import ValidationResult
from sqlopt.platforms.sql.semantic_equivalence import build_semantic_equivalence
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
                    "sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates",
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
                    "sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates",
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
                    "sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates",
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

    def test_optimize_stage_uses_replay_cassette_and_marks_replay_trace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_replay_") as td:
            run_dir = Path(td)
            cassette_root = Path(td) / "cassettes"
            proposal = {
                "sqlKey": "demo.user.listUsers",
                "statementKey": "demo.user.listUsers",
                "issues": [{"code": "SEQ_SCAN"}],
                "dbEvidenceSummary": {
                    "tables": ["users"],
                    "indexes": [{"table": "users", "name": "idx_users_status"}],
                },
                "planSummary": {"risk": "low"},
                "suggestions": [{"strategy": "index"}],
                "verdict": "ACTIONABLE",
                "actionability": {"score": 85, "tier": "HIGH", "autoPatchLikelihood": "HIGH", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": 0,
            }
            sql_unit = _sql_unit()
            llm_cfg = {
                "enabled": True,
                "mode": "replay",
                "provider": "opencode_run",
                "opencode_model": "test-model",
                "cassette_root": str(cassette_root),
            }
            request = {
                "sqlKey": sql_unit["sqlKey"],
                "sql": sql_unit["sql"],
                "templateSql": sql_unit["templateSql"],
                "dynamicFeatures": sql_unit["dynamicFeatures"],
                "stableDbEvidence": {
                    "tables": proposal["dbEvidenceSummary"]["tables"],
                    "indexes": proposal["dbEvidenceSummary"]["indexes"],
                    "planSummary": proposal["planSummary"],
                },
                "promptVersion": "v1",
                "provider": llm_cfg["provider"],
                "model": llm_cfg["opencode_model"],
            }
            fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(request))
            cassette_root.joinpath(optimize_raw_cassette_path(cassette_root, fingerprint).relative_to(cassette_root)).parent.mkdir(parents=True, exist_ok=True)
            cassette_root.joinpath(optimize_normalized_cassette_path(cassette_root, fingerprint).relative_to(cassette_root)).parent.mkdir(parents=True, exist_ok=True)
            cassette_root.joinpath(optimize_raw_cassette_path(cassette_root, fingerprint).relative_to(cassette_root)).write_text(
                json.dumps(
                    {
                        "fingerprint": fingerprint,
                        "provider": llm_cfg["provider"],
                        "model": llm_cfg["opencode_model"],
                        "promptVersion": "v1",
                        "sqlKey": sql_unit["sqlKey"],
                        "request": request,
                        "response": {"candidates": []},
                        "createdAt": "2026-04-09T00:00:00Z",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            cassette_root.joinpath(optimize_normalized_cassette_path(cassette_root, fingerprint).relative_to(cassette_root)).write_text(
                json.dumps(
                    {
                        "fingerprint": fingerprint,
                        "sqlKey": sql_unit["sqlKey"],
                        "rawCandidateCount": 0,
                        "validCandidates": [],
                        "trace": {"executor": "opencode_run", "provider": "opencode_run", "task_id": f"{sql_unit['sqlKey']}:opt"},
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch(
                    "sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates",
                    side_effect=AssertionError("live provider should not be called"),
                ):
                    proposal_row = optimize.execute_one(
                        sql_unit,
                        run_dir,
                        self._validator(),
                        config={"llm": llm_cfg, "project": {}, "db": {"platform": "postgresql"}},
                    )

            trace_ref = (proposal_row.get("llmTraceRefs") or [None])[0]
            self.assertTrue(trace_ref)
            trace_path = run_dir / str(trace_ref)
            self.assertTrue(trace_path.exists())
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace.get("executor"), "replay")
            self.assertEqual(trace.get("provider"), "cassette")
            self.assertEqual(trace.get("replaySourceExecutor"), "opencode_run")
            self.assertEqual(trace.get("replaySourceProvider"), "opencode_run")
            self.assertIn("candidateGenerationDiagnostics", proposal_row)

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
                    "sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates",
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

    def test_optimize_stage_persists_low_value_assessments_into_proposal_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_opt_low_value_artifact_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.findUsersByKeyword"
            sql_unit["statementKey"] = "demo.user.advanced.findUsersByKeyword"
            sql_unit["sql"] = (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users AS u WHERE status != 'DELETED' ORDER BY created_at DESC"
            )
            sql_unit["templateSql"] = (
                "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
                "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
                "<when test=\"status != null and status != ''\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where> ORDER BY created_at DESC"
            )
            sql_unit["dynamicFeatures"] = ["BIND", "INCLUDE", "WHERE", "CHOOSE"]
            proposal = {
                "sqlKey": "demo.user.advanced.findUsersByKeyword",
                "statementKey": "demo.user.advanced.findUsersByKeyword",
                "issues": [],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [],
                "verdict": "NOOP",
                "actionability": {"score": 40, "tier": "LOW", "autoPatchLikelihood": "LOW", "reasons": [], "blockedBy": []},
                "recommendedSuggestionIndex": None,
            }
            llm_candidates = [
                {
                    "id": "opt-001",
                    "source": "llm",
                    "rewriteStrategy": "union_or_split",
                    "rewrittenSql": (
                        "SELECT id, name, email, status, created_at, updated_at "
                        "FROM users AS u WHERE name ILIKE #{keywordPattern} OR status = #{status} "
                        "ORDER BY created_at DESC"
                    ),
                }
            ]
            trace = {"executor": "opencode_run", "provider": "opencode_run"}
            with patch("sqlopt.stages.optimize.generate_proposal", return_value=proposal):
                with patch("sqlopt.platforms.sql.llm_replay_gateway.generate_llm_candidates", return_value=(llm_candidates, trace)):
                    optimize.execute_one(
                        sql_unit,
                        run_dir,
                        self._validator(),
                        config={"llm": {"enabled": True, "provider": "opencode_run"}, "project": {}},
                    )

            proposal_row = json.loads((run_dir / "artifacts" / "proposals.jsonl").read_text(encoding="utf-8").splitlines()[0])
            diagnostics = proposal_row["candidateGenerationDiagnostics"]
            self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
            self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
            self.assertEqual(
                diagnostics["lowValueAssessments"],
                [
                    {
                        "candidate_id": "opt-001",
                        "rule_id": "DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                        "category": "DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                        "reason": "candidate rewrites dynamic filter predicates without a safe template-preserving baseline",
                    }
                ],
            )

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

    def test_validate_stage_verifies_predicate_and_order_reordering_case(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_ordering_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.order.harness.listOrdersWithUsersPaged"
            sql_unit["statementKey"] = "demo.order.harness.listOrdersWithUsersPaged"
            original_sql = (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) "
                "AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            )
            rewritten_sql = (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE o.status = #{status} "
                "AND (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            )
            semantic_equivalence = build_semantic_equivalence(
                original_sql=original_sql,
                rewritten_sql=rewritten_sql,
                equivalence={
                    "checked": True,
                    "method": "sql_semantic_compare_v2",
                    "rowCount": {"status": "MATCH"},
                    "keySetHash": {"status": "MATCH"},
                    "rowSampleHash": {"status": "MATCH"},
                    "evidenceRefs": [],
                },
            )
            result = ValidationResult(
                sql_key="demo.order.harness.listOrdersWithUsersPaged",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="llm",
                warnings=[],
                risk_flags=[],
                rewritten_sql=rewritten_sql,
                selected_candidate_id="c1",
                semantic_equivalence=semantic_equivalence,
                decision_layers={
                    "feasibility": {"candidateAvailable": True, "dbReachable": True, "ready": True},
                    "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                    "delivery": {"selectedCandidateSource": "llm", "selectedCandidateId": "c1"},
                    "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                },
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(sql_unit, {}, run_dir, self._validator(), db_reachable=True, config={})
                rows = self._ledger_rows(run_dir)
                convergence_rows = [
                    json.loads(line)
                    for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]

        self.assertEqual(rows[0]["phase"], "validate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
        self.assertEqual(rows[0]["inputs"]["semantic_gate_status"], "PASS")
        self.assertEqual(convergence_rows[0]["semanticGate"]["passCount"], 1)

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
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_validate_convergence_keeps_choose_filter_select_cleanup_manual_review_when_shape_family_is_not_targeted(self) -> None:
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
            sql_unit["dynamicRenderIdentity"] = {
                "surfaceType": "CHOOSE_BRANCH_BODY",
                "renderMode": "CHOOSE_BRANCH_RENDERED",
                "chooseOrdinal": 0,
                "branchOrdinal": 0,
                "branchKind": "WHEN",
                "branchTestFingerprint": "status != null",
                "renderedBranchSql": "status = #{status}",
                "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                "requiredSiblingShape": {"branchCount": 2},
            }
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")

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

    def test_validate_convergence_keeps_supported_choose_filter_case_blocked_as_low_value_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_batch5_choose_blocked_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.user.advanced.findUsersByKeyword"
            sql_unit["statementKey"] = "demo.user.advanced.findUsersByKeyword"
            sql_unit["sql"] = (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE status != 'DELETED' ORDER BY created_at DESC"
            )
            sql_unit["dynamicFeatures"] = ["BIND", "INCLUDE", "WHERE", "CHOOSE"]
            sql_unit["templateSql"] = (
                "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
                "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
                "<when test=\"status != null and status != ''\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where> ORDER BY created_at DESC"
            )
            proposal = {
                "sqlKey": "demo.user.advanced.findUsersByKeyword",
                "statementKey": "demo.user.advanced.findUsersByKeyword",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 3,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.user.advanced.findUsersByKeyword",
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
        self.assertEqual(convergence_rows[0]["shapeFamily"], "IF_GUARDED_FILTER_STATEMENT")
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY")

    def test_validate_convergence_keeps_bare_choose_case_blocked_as_validate_semantic_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_batch7_choose_semantic_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.test.complex.chooseBasic"
            sql_unit["statementKey"] = "demo.test.complex.chooseBasic"
            sql_unit["sql"] = "SELECT id, name FROM users WHERE 1=1"
            sql_unit["dynamicFeatures"] = ["CHOOSE"]
            sql_unit["templateSql"] = (
                "SELECT id, name FROM users <choose>"
                "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
                "<when test=\"type == 'inactive'\">WHERE status = 'inactive'</when>"
                "<otherwise>WHERE 1=1</otherwise>"
                "</choose>"
            )
            proposal = {
                "sqlKey": "demo.test.complex.chooseBasic",
                "statementKey": "demo.test.complex.chooseBasic",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 3,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.test.complex.chooseBasic",
                status="NEED_MORE_PARAMS",
                equivalence={"checked": False},
                perf_comparison={"checked": False, "reasonCodes": ["VALIDATE_SEMANTIC_ERROR"]},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="medium",
                feedback={"reason_code": "VALIDATE_SEMANTIC_ERROR", "message": "semantic check error, manual review required"},
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql=sql_unit["sql"],
                selected_candidate_id=None,
                semantic_equivalence={"status": "UNCERTAIN", "confidence": "LOW", "evidenceLevel": "STRUCTURE"},
                decision_layers={
                    "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                    "evidence": {"semanticChecked": False, "perfChecked": False, "degraded": True},
                    "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                    "acceptance": {"status": "NEED_MORE_PARAMS", "validationProfile": "balanced"},
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "VALIDATE_SEMANTIC_ERROR")

    def test_validate_convergence_preserves_explicit_unsupported_choose_tail_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_batch5_choose_unsupported_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.test.complex.chooseWithLimit"
            sql_unit["statementKey"] = "demo.test.complex.chooseWithLimit"
            sql_unit["sql"] = "SELECT id, name FROM users WHERE status = 'active' LIMIT #{limit}"
            sql_unit["dynamicFeatures"] = ["CHOOSE", "IF"]
            sql_unit["templateSql"] = (
                "SELECT id, name FROM users <choose>"
                "<when test=\"statusFilter == 'active'\">WHERE status = 'active'</when>"
                "<when test=\"statusFilter == 'pending'\">WHERE status = 'pending'</when>"
                "<otherwise>WHERE 1=1</otherwise>"
                "</choose> <if test=\"limit != null\">LIMIT #{limit}</if>"
            )
            proposal = {
                "sqlKey": "demo.test.complex.chooseWithLimit",
                "statementKey": "demo.test.complex.chooseWithLimit",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "EMPTY_CANDIDATES",
                    "recoveryReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY",
                    "rawCandidateCount": 0,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.test.complex.chooseWithLimit",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT id, name FROM users WHERE status = 'active' LIMIT #{limit}",
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_validate_convergence_reports_batch6_candidate_gap_without_not_target_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_batch6_candidate_gap_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.test.complex.includeSimple"
            sql_unit["statementKey"] = "demo.test.complex.includeSimple"
            sql_unit["sql"] = "SELECT * FROM users"
            sql_unit["templateSql"] = 'SELECT <include refid="BaseColumns"/> FROM users'
            sql_unit["dynamicFeatures"] = ["INCLUDE"]
            proposal = {
                "sqlKey": "demo.test.complex.includeSimple",
                "statementKey": "demo.test.complex.includeSimple",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 2,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.test.complex.includeSimple",
                status="PASS",
                equivalence={"checked": True},
                perf_comparison={"checked": True, "reasonCodes": []},
                security_checks={"dollar_substitution_removed": True},
                semantic_risk="low",
                feedback=None,
                selected_candidate_source="rule",
                warnings=[],
                risk_flags=[],
                rewritten_sql="SELECT * FROM users",
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY")

    def test_validate_convergence_reclassifies_in_subquery_wording_drift_as_unsupported_strategy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_in_subquery_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.test.complex.inSubquery"
            sql_unit["statementKey"] = "demo.test.complex.inSubquery"
            sql_unit["sql"] = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
            sql_unit["dynamicFeatures"] = []
            sql_unit["templateSql"] = sql_unit["sql"]
            proposal = {
                "sqlKey": "demo.test.complex.inSubquery",
                "statementKey": "demo.test.complex.inSubquery",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY",
                    "rawCandidateCount": 2,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.test.complex.inSubquery",
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_validate_convergence_keeps_batch6_boundary_statement_blocked_as_not_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_validate_batch6_boundary_") as td:
            run_dir = Path(td)
            sql_unit = _sql_unit()
            sql_unit["sqlKey"] = "demo.shipment.harness.findShipmentsByOrderIds"
            sql_unit["statementKey"] = "demo.shipment.harness.findShipmentsByOrderIds"
            sql_unit["sql"] = "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments AS s WHERE order_id IN (#{orderId})"
            sql_unit["templateSql"] = (
                'SELECT <include refid="ShipmentHarnessColumns" /> FROM shipments AS s '
                '<where><foreach collection="orderIds" item="orderId">#{orderId}</foreach></where>'
            )
            sql_unit["dynamicFeatures"] = ["INCLUDE", "WHERE", "FOREACH"]
            proposal = {
                "sqlKey": "demo.shipment.harness.findShipmentsByOrderIds",
                "statementKey": "demo.shipment.harness.findShipmentsByOrderIds",
                "llmCandidates": [],
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 1,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                },
            }
            result = ValidationResult(
                sql_key="demo.shipment.harness.findShipmentsByOrderIds",
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
        self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
        self.assertEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")

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

    def test_validate_convergence_locks_batch6_candidate_selection_and_boundary_blockers(self) -> None:
        cases = [
            {
                "sqlKey": "demo.test.complex.staticSimpleSelect",
                "statementKey": "demo.test.complex.staticSimpleSelect",
                "sql": "SELECT id, name, email, status, created_at FROM users",
                "templateSql": "SELECT id, name, email, status, created_at FROM users",
                "dynamicFeatures": [],
                "proposal": {
                    "candidateGenerationDiagnostics": {
                        "degradationKind": "EMPTY_CANDIDATES",
                        "recoveryReason": "NO_SAFE_BASELINE_SHAPE_MATCH",
                        "rawCandidateCount": 0,
                        "acceptedCandidateCount": 0,
                        "finalCandidateCount": 0,
                    }
                },
                "result": ValidationResult(
                    sql_key="demo.test.complex.staticSimpleSelect",
                    status="PASS",
                    equivalence={"checked": True},
                    perf_comparison={"checked": True, "reasonCodes": []},
                    security_checks={"dollar_substitution_removed": True},
                    semantic_risk="low",
                    feedback=None,
                    selected_candidate_source="rule",
                    warnings=[],
                    risk_flags=[],
                    rewritten_sql="SELECT id, name, email, status, created_at FROM users",
                    selected_candidate_id=None,
                    semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                    decision_layers={
                        "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                        "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                        "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                        "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                    },
                ),
                "expected": "NO_SAFE_BASELINE_RECOVERY",
            },
            {
                "sqlKey": "demo.order.harness.findOrdersByNos",
                "statementKey": "demo.order.harness.findOrdersByNos",
                "sql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo}",
                "templateSql": (
                    "SELECT <include refid=\"OrderHarnessColumns\" /> FROM orders "
                    "<where><foreach collection=\"orderNos\" item=\"orderNo\" open=\"order_no IN (\" separator=\",\" close=\")\">"
                    "#{orderNo}</foreach></where>"
                ),
                "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
                "proposal": {
                    "candidateGenerationDiagnostics": {
                        "degradationKind": "EMPTY_CANDIDATES",
                        "recoveryReason": "NO_SAFE_BASELINE_SHAPE_MATCH",
                        "rawCandidateCount": 0,
                        "acceptedCandidateCount": 0,
                        "finalCandidateCount": 0,
                    }
                },
                "result": ValidationResult(
                    sql_key="demo.order.harness.findOrdersByNos",
                    status="PASS",
                    equivalence={"checked": True},
                    perf_comparison={"checked": True, "reasonCodes": []},
                    security_checks={"dollar_substitution_removed": True},
                    semantic_risk="low",
                    feedback=None,
                    selected_candidate_source="rule",
                    warnings=[],
                    risk_flags=[],
                    rewritten_sql="SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo}",
                    selected_candidate_id=None,
                    semantic_equivalence={"status": "PASS", "confidence": "HIGH", "evidenceLevel": "DB_FINGERPRINT"},
                    decision_layers={
                        "feasibility": {"candidateAvailable": False, "dbReachable": True, "ready": False},
                        "evidence": {"semanticChecked": True, "perfChecked": True, "degraded": False},
                        "delivery": {"selectedCandidateSource": "rule", "selectedCandidateId": None},
                        "acceptance": {"status": "PASS", "validationProfile": "balanced"},
                    },
                ),
                "expected": "SHAPE_FAMILY_NOT_TARGET",
            },
        ]

        for case in cases:
            with self.subTest(sql_key=case["sqlKey"]):
                with tempfile.TemporaryDirectory(prefix=f"sqlopt_verification_{case['sqlKey'].replace('.', '_')}_") as td:
                    run_dir = Path(td)
                    sql_unit = _sql_unit()
                    sql_unit["sqlKey"] = case["sqlKey"]
                    sql_unit["statementKey"] = case["statementKey"]
                    sql_unit["sql"] = case["sql"]
                    sql_unit["templateSql"] = case["templateSql"]
                    sql_unit["dynamicFeatures"] = case["dynamicFeatures"]
                    with patch("sqlopt.stages.validate.validate_proposal", return_value=case["result"]):
                        validate.execute_one(sql_unit, case["proposal"], run_dir, self._validator(), db_reachable=True, config={})

                    convergence_rows = [
                        json.loads(line)
                        for line in (run_dir / "artifacts" / "statement_convergence.jsonl").read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]

                self.assertEqual(convergence_rows[0]["convergenceDecision"], "MANUAL_REVIEW")
                self.assertEqual(convergence_rows[0]["conflictReason"], case["expected"])
                if case["expected"] == "SHAPE_FAMILY_NOT_TARGET":
                    self.assertEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")
                else:
                    self.assertNotEqual(convergence_rows[0]["conflictReason"], "SHAPE_FAMILY_NOT_TARGET")

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
