from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.contracts import ContractValidator
from sqlopt.platforms.sql.models import ValidationResult
from sqlopt.stages import optimize, patch_generate, scan, validate

ROOT = Path(__file__).resolve().parents[1]


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
        ledger = run_dir / "verification" / "ledger.jsonl"
        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]

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
                decision_layers={"acceptance": {"status": "PASS"}},
            )
            with patch("sqlopt.stages.validate.validate_proposal", return_value=result):
                validate.execute_one(_sql_unit(), {}, run_dir, self._validator(), db_reachable=False, config={})
                rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "validate")
        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_patch_stage_writes_verification_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_verification_patch_") as td:
            run_dir = Path(td)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            acceptance = {
                "sqlKey": "demo.user.listUsers#v1",
                "status": "FAIL",
                "equivalence": {"checked": True},
                "perfComparison": {"checked": True, "reasonCodes": []},
                "securityChecks": {"dollar_substitution_removed": True},
            }
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text(
                json.dumps(acceptance, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            patch_generate.execute_one(_sql_unit(), acceptance, run_dir, self._validator())
            rows = self._ledger_rows(run_dir)

        self.assertEqual(rows[0]["phase"], "patch_generate")
        self.assertEqual(rows[0]["status"], "VERIFIED")
