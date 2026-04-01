from __future__ import annotations

import unittest

import sqlopt.platforms.sql.models as sql_models
import sqlopt.stages.report_interfaces as report_interfaces


class ContractModelInterfacesTest(unittest.TestCase):
    def test_sql_model_exports_use_to_contract_only(self) -> None:
        evaluation = sql_models.CandidateEvaluation(
            candidate_id="c1",
            source="llm",
            semantic_match=True,
            improved=True,
            after_cost=8.0,
        )
        equivalence = sql_models.EquivalenceCheck(
            checked=True,
            method="static",
            row_count={"status": "MATCH"},
            evidence_refs=[],
        )
        perf = sql_models.PerfComparison(
            checked=True,
            method="heuristic",
            before_summary={},
            after_summary={},
            reason_codes=[],
            improved=True,
            evidence_refs=[],
        )
        selection = sql_models.CandidateSelectionResult(
            rewritten_sql="SELECT id FROM users",
            selected_candidate_id="c1",
            selected_candidate_source="llm",
            candidate_evaluations=[evaluation],
            equivalence=equivalence,
            perf=perf,
        )
        # ValidationResult no longer includes patch-related fields like rewrite_facts
        result = sql_models.ValidationResult(
            sql_key="demo.user.listUsers#v1",
            status="PASS",
            rewritten_sql="SELECT id FROM users",
            equivalence=equivalence.to_contract(),
            perf_comparison=perf.to_contract(),
            security_checks={"dollar_substitution_removed": True},
            semantic_risk="low",
            feedback=None,
            selected_candidate_source="llm",
            warnings=[],
            risk_flags=[],
            candidate_selection_trace=[{"candidateId": "c1"}],
        )

        self.assertTrue(hasattr(evaluation, "to_contract"))
        self.assertTrue(hasattr(equivalence, "to_contract"))
        self.assertTrue(hasattr(perf, "to_contract"))
        self.assertTrue(hasattr(result, "to_contract"))
        self.assertFalse(hasattr(evaluation, "as_dict"))
        self.assertFalse(hasattr(equivalence, "as_dict"))
        self.assertFalse(hasattr(perf, "as_dict"))
        self.assertFalse(hasattr(selection, "candidate_evaluations_payload"))
        self.assertEqual(selection.candidate_evaluations_to_contract()[0]["candidateId"], "c1")
        self.assertEqual(result.to_contract()["sqlKey"], "demo.user.listUsers#v1")
        # rewrite_facts is no longer in ValidationResult - it's computed by patch_generate stage
        self.assertNotIn("rewriteFacts", result.to_contract())
        self.assertNotIn("patchStrategyCandidates", result.to_contract())
        self.assertNotIn("patchTarget", result.to_contract())
        self.assertNotIn("canonicalizationAssessment", result.to_contract())
        self.assertEqual(result.to_contract()["candidateSelectionTrace"][0]["candidateId"], "c1")

    def test_report_model_exports_use_to_contract_only(self) -> None:
        failure = report_interfaces.FailureRecord(
            sql_key="demo.user.listUsers#v1",
            reason_code="VALIDATE_PERF_NOT_IMPROVED",
            status="NEED_MORE_PARAMS",
            classification="degradable",
            phase="validate",
        )
        report = report_interfaces.RunReportDocument(
            run_id="run_demo",
            generated_at="2026-03-03T00:00:00+00:00",
            target_stage="report",
            status="DONE",
            verdict="BLOCKED",
            next_action="inspect",
            phase_status={"scan": "DONE", "report": "DONE"},
            stats={
                "sql_units": 1,
                "proposals": 1,
                "acceptance_pass": 0,
                "patch_applicable_count": 0,
                "patch_files": 0,
                "blocked_sql_count": 1,
            },
            top_blockers=[{"code": "VALIDATE_PERF_NOT_IMPROVED", "count": 1}],
        )
        artifacts = report_interfaces.ReportArtifacts(
            report=report,
            failures=[failure],
            state=report_interfaces.ReportStateSnapshot(phase_status={}, attempts_by_phase={}),
            next_actions=[],
            top_blockers=[],
            sql_rows=[],
            proposal_rows=[],
        )

        self.assertTrue(hasattr(failure, "to_contract"))
        self.assertTrue(hasattr(report, "to_contract"))
        self.assertFalse(hasattr(failure, "as_dict"))
        self.assertFalse(hasattr(report, "as_dict"))
        self.assertFalse(hasattr(artifacts, "failures_payload"))
        self.assertEqual(artifacts.failures_to_contract()[0]["phase"], "validate")
        self.assertEqual(report.to_contract()["verdict"], "BLOCKED")
        self.assertEqual(report.to_contract()["stats"]["sql_total"], 1)


if __name__ == "__main__":
    unittest.main()
