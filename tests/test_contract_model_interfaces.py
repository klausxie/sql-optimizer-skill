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

    def test_report_model_exports_use_to_contract_only(self) -> None:
        failure = report_interfaces.FailureRecord(
            sql_key="demo.user.listUsers#v1",
            reason_code="VALIDATE_PERF_NOT_IMPROVED",
            status="NEED_MORE_PARAMS",
            classification="degradable",
            phase="validate",
        )
        summary = report_interfaces.RunReportSummary(
            generated_at="2026-03-03T00:00:00+00:00",
            verdict="BLOCKED",
            release_readiness="NO_GO",
            top_blockers=[],
            next_actions=[],
            prioritized_sql_keys=[],
        )
        items = report_interfaces.RunReportItems(units=[], proposals=[], acceptance=[], patches=[])
        report = report_interfaces.RunReportDocument(
            run_id="run_demo",
            mode="analyze",
            llm_gate=None,
            policy={},
            stats={},
            items=items,
            summary=summary,
            contract_version="v1",
        )
        topology = report_interfaces.OpsTopologyDocument(
            run_id="run_demo",
            executor="python",
            subagents={"optimize": False, "validate": False},
            llm_mode="disabled",
            llm_gate=None,
            runtime_policy={},
        )
        health = report_interfaces.OpsHealthDocument(
            run_id="run_demo",
            mode="analyze",
            generated_at="2026-03-03T00:00:00+00:00",
            status="ok",
            failure_count=0,
            fatal_failure_count=0,
            retryable_failure_count=0,
            degradable_count=0,
            report_json="runs/run_demo/report.json",
        )
        artifacts = report_interfaces.ReportArtifacts(
            report=report,
            topology=topology,
            health=health,
            failures=[failure],
            state=report_interfaces.ReportStateSnapshot(phase_status={}, attempts_by_phase={}),
            next_actions=[],
            top_blockers=[],
            sql_rows=[],
            proposal_rows=[],
        )

        self.assertTrue(hasattr(failure, "to_contract"))
        self.assertTrue(hasattr(report, "to_contract"))
        self.assertTrue(hasattr(topology, "to_contract"))
        self.assertTrue(hasattr(health, "to_contract"))
        self.assertFalse(hasattr(failure, "as_dict"))
        self.assertFalse(hasattr(report, "as_dict"))
        self.assertFalse(hasattr(artifacts, "failures_payload"))
        self.assertEqual(artifacts.failures_to_contract()[0]["phase"], "validate")
        self.assertEqual(report.to_contract()["summary"]["verdict"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
