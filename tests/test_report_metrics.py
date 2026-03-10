from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_metrics import (
    build_failures,
    summarize_semantic_confidence_upgrades,
    summarize_semantic_gate_quality,
    summarize_semantic_gates,
    build_verification_gate,
    count_llm_timeouts,
    summarize_failures,
)
from sqlopt.stages.report_models import ManifestEvent


class ReportMetricsTest(unittest.TestCase):
    def test_count_llm_timeouts_counts_timeout_and_budget_exhausted_traces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_metrics_timeout_") as td:
            run_dir = Path(td)
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            trace_1 = run_dir / "pipeline" / "ops" / "trace_1.json"
            trace_1.write_text(json.dumps({"degrade_reason": "RUN_TIME_BUDGET_EXHAUSTED"}), encoding="utf-8")
            trace_2 = run_dir / "pipeline" / "ops" / "trace_2.json"
            trace_2.write_text(json.dumps({"response": {"error_type": "TimeoutError"}}), encoding="utf-8")
            proposals = [{"llmTraceRefs": ["pipeline/ops/trace_1.json", "pipeline/ops/trace_2.json"]}]
            self.assertEqual(count_llm_timeouts(run_dir, proposals), 2)

    def test_build_and_summarize_failures_merge_acceptance_and_manifest(self) -> None:
        acceptance = [
            {"sqlKey": "demo.user.find#v1", "status": "FAIL", "feedback": {"reason_code": "VALIDATE_SEMANTIC_ERROR"}},
            {"sqlKey": "demo.user.find#v2", "status": "NEED_MORE_PARAMS"},
            {"sqlKey": "demo.user.find#v3", "status": "PASS"},
        ]
        manifest_rows = [
            ManifestEvent(stage="scan", event="failed", payload={"reason_code": "RUNTIME_RETRY_EXHAUSTED", "statement_key": "demo.user.find"}),
            ManifestEvent(stage="optimize", event="done", payload={}),
        ]
        failures = build_failures(acceptance, manifest_rows)
        self.assertEqual(len(failures), 3)
        reason_counts, phase_reason_counts, class_counts = summarize_failures(failures)
        self.assertEqual(reason_counts["VALIDATE_SEMANTIC_ERROR"], 1)
        self.assertEqual(reason_counts["VALIDATE_PARAM_INSUFFICIENT"], 1)
        self.assertEqual(reason_counts["RUNTIME_RETRY_EXHAUSTED"], 1)
        self.assertEqual(phase_reason_counts["validate"]["VALIDATE_SEMANTIC_ERROR"], 1)
        self.assertEqual(phase_reason_counts["scan"]["RUNTIME_RETRY_EXHAUSTED"], 1)
        self.assertEqual(class_counts["retryable"], 1)

    def test_build_verification_gate_reports_warnings_and_confidence(self) -> None:
        acceptance_rows = [{"sqlKey": "demo.user.find#v1", "status": "PASS"}]
        patch_rows = [{"sqlKey": "demo.user.find#v1", "applicable": True}]
        verification_rows = [
            {"sql_key": "demo.user.find#v1", "phase": "validate", "status": "UNVERIFIED"},
            {"sql_key": "demo.user.find#v1", "phase": "patch_generate", "status": "UNVERIFIED"},
            {"sql_key": "demo.user.find#v1", "phase": "optimize", "status": "PARTIAL", "reason_code": "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR"},
        ]
        warnings, confidence, gate = build_verification_gate(acceptance_rows, patch_rows, verification_rows)
        self.assertEqual(confidence, "LOW")
        self.assertTrue(any("UNVERIFIED_PASS_ACCEPTANCE" in row for row in warnings))
        self.assertTrue(any("UNVERIFIED_APPLICABLE_PATCH" in row for row in warnings))
        self.assertTrue(any("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR" in row for row in warnings))
        self.assertEqual(gate["unverified_pass_count"], 1)
        self.assertEqual(gate["unverified_applicable_patch_count"], 1)
        self.assertEqual(gate["critical_unverified_sql_keys"], ["demo.user.find#v1"])

    def test_summarize_semantic_gates_counts_statuses_and_reason_codes(self) -> None:
        acceptance_rows = [
            {
                "sqlKey": "demo.user.find#v1",
                "semanticEquivalence": {"status": "PASS", "reasons": ["SEMANTIC_PREDICATE_STABLE"]},
            },
            {
                "sqlKey": "demo.user.find#v2",
                "semanticEquivalence": {"status": "UNCERTAIN", "reasons": ["SEMANTIC_PROJECTION_CHANGED"]},
            },
            {
                "sqlKey": "demo.user.find#v3",
                "semanticEquivalence": {"status": "FAIL", "reasons": ["SEMANTIC_PREDICATE_ADDED_OR_REMOVED"]},
            },
            {"sqlKey": "demo.user.find#v4"},
        ]
        counts, reason_counts = summarize_semantic_gates(acceptance_rows)
        self.assertEqual(counts["pass"], 2)
        self.assertEqual(counts["uncertain"], 1)
        self.assertEqual(counts["fail"], 1)
        self.assertEqual(reason_counts["SEMANTIC_PROJECTION_CHANGED"], 1)
        self.assertEqual(reason_counts["SEMANTIC_PREDICATE_ADDED_OR_REMOVED"], 1)

    def test_summarize_semantic_gate_quality_counts_confidence_evidence_and_conflicts(self) -> None:
        acceptance_rows = [
            {
                "sqlKey": "demo.user.find#v1",
                "semanticEquivalence": {
                    "status": "PASS",
                    "confidence": "HIGH",
                    "evidenceLevel": "DB_FINGERPRINT",
                    "hardConflicts": [],
                },
            },
            {
                "sqlKey": "demo.user.find#v2",
                "semanticEquivalence": {
                    "status": "FAIL",
                    "confidence": "HIGH",
                    "evidenceLevel": "DB_COUNT",
                    "hardConflicts": ["SEMANTIC_ROW_COUNT_MISMATCH"],
                },
            },
            {"sqlKey": "demo.user.find#v3"},
        ]
        confidence, evidence_level, conflicts = summarize_semantic_gate_quality(acceptance_rows)
        self.assertEqual(confidence["HIGH"], 2)
        self.assertEqual(confidence["UNKNOWN"], 1)
        self.assertEqual(evidence_level["DB_FINGERPRINT"], 1)
        self.assertEqual(evidence_level["DB_COUNT"], 1)
        self.assertEqual(evidence_level["UNKNOWN"], 1)
        self.assertEqual(conflicts["SEMANTIC_ROW_COUNT_MISMATCH"], 1)

    def test_build_failures_includes_low_confidence_pass_gate(self) -> None:
        acceptance = [
            {
                "sqlKey": "demo.user.find#v1",
                "status": "PASS",
                "semanticEquivalence": {"status": "PASS", "confidence": "LOW"},
            }
        ]
        failures = build_failures(acceptance, manifest_rows=[])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].reason_code, "VALIDATE_SEMANTIC_CONFIDENCE_LOW")

    def test_summarize_semantic_confidence_upgrades_counts_sources(self) -> None:
        acceptance_rows = [
            {
                "sqlKey": "demo.user.find#v1",
                "semanticEquivalence": {
                    "confidenceUpgradeApplied": True,
                    "confidenceUpgradeEvidenceSources": ["DB_FINGERPRINT"],
                },
            },
            {
                "sqlKey": "demo.user.find#v2",
                "semanticEquivalence": {
                    "confidenceUpgradeApplied": True,
                    "confidenceUpgradeReasons": ["SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_PARTIAL"],
                },
            },
            {
                "sqlKey": "demo.user.find#v3",
                "semanticEquivalence": {
                    "confidenceUpgradeApplied": False,
                },
            },
        ]
        upgraded_count, by_source = summarize_semantic_confidence_upgrades(acceptance_rows)
        self.assertEqual(upgraded_count, 2)
        self.assertEqual(by_source["DB_FINGERPRINT"], 2)


if __name__ == "__main__":
    unittest.main()
