from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ManifestEvent, ReportInputs, ReportStateSnapshot


class ReportBuilderTest(unittest.TestCase):
    def test_build_report_artifacts_aggregates_failures_and_phase_coverage(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [{"code": "SELECT_STAR"}],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 85,
                        "tier": "HIGH",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT"},
                    "repairability": {"status": "REPAIRABLE"},
                    "perfComparison": {"reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "semanticEquivalence": {"status": "UNCERTAIN", "reasons": ["SEMANTIC_ROW_COUNT_UNVERIFIED"]},
                    "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "statementKey": "demo.user.listUsers",
                    "applicable": True,
                    "deliveryOutcome": {"tier": "READY_TO_APPLY", "summary": "patch is ready to apply"},
                }
            ],
            state=ReportStateSnapshot(
                phase_status={"preflight": "DONE", "scan": "DONE", "report": "DONE"},
                attempts_by_phase={"report": 1},
                selection_scope={"present": True, "mapper_paths": ["src/main/resources/demo_mapper.xml"], "sql_keys": [], "scanned_count": 2, "selected_count": 1},
            ),
            manifest_rows=[
                ManifestEvent(
                    stage="preflight",
                    event="failed",
                    payload={"reason_code": "PREFLIGHT_SCANNER_MISSING"},
                )
            ],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.listUsers#v1",
                    "statement_key": "demo.user.listUsers",
                    "phase": "validate",
                    "status": "PARTIAL",
                    "reason_code": "VALIDATE_DB_UNREACHABLE",
                    "reason_message": "degraded DB fallback",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["sql_units"], 1)
        self.assertEqual(artifacts.report.selection_scope["selected_count"], 1)
        self.assertEqual(artifacts.report.stats["acceptance_need_more_params"], 1)
        self.assertEqual(artifacts.report.stats["semantic_gate_uncertain_count"], 1)
        self.assertEqual(artifacts.report.stats["semantic_gate_pass_count"], 0)
        self.assertEqual(artifacts.report.stats["semantic_gate_fail_count"], 0)
        self.assertEqual(artifacts.report.stats["semantic_gate_reason_counts"]["SEMANTIC_ROW_COUNT_UNVERIFIED"], 1)
        self.assertEqual(artifacts.report.stats["semantic_confidence_distribution"]["UNKNOWN"], 1)
        self.assertEqual(artifacts.report.stats["semantic_evidence_level_distribution"]["UNKNOWN"], 1)
        self.assertEqual(artifacts.report.stats["semantic_hard_conflict_top_codes"], {})
        self.assertEqual(artifacts.report.stats["confidence_upgraded_count"], 0)
        self.assertEqual(artifacts.report.stats["confidence_upgrade_rate"], 0.0)
        self.assertEqual(artifacts.report.stats["confidence_upgrade_by_evidence_source"], {})
        self.assertEqual(artifacts.report.stats["repairable_blocked_count"], 1)
        self.assertEqual(artifacts.report.stats["uncertain_upgrade_count"], 0)
        self.assertEqual(artifacts.report.stats["semantic_false_block_recovered_count"], 0)
        self.assertEqual(artifacts.report.stats["include_safe_materialized_count"], 0)
        self.assertEqual(artifacts.report.stats["patchability_lift_rate"], 1.0)
        self.assertEqual(artifacts.report.stats["preflight_failure_count"], 1)
        self.assertEqual(artifacts.report.stats["pipeline_coverage"]["report"], "DONE")
        self.assertEqual(artifacts.report.stats["blocker_family_counts"], {"READY": 1})
        self.assertEqual(artifacts.report.stats["candidate_degradation_counts"], {})
        self.assertEqual(artifacts.report.stats["candidate_recovery_counts"], {})
        self.assertEqual(artifacts.report.stats["empty_candidate_recovered_count"], 0)
        self.assertEqual(artifacts.report.stats["text_fallback_recovered_count"], 0)
        self.assertEqual(artifacts.report.stats["aggregation_shape_counts"], {})
        self.assertEqual(artifacts.report.stats["aggregation_constraint_counts"], {})
        self.assertEqual(artifacts.report.stats["aggregation_safe_baseline_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_baseline_family_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_delivery_class_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_ready_baseline_family_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_ready_patch_count"], 0)
        self.assertEqual(artifacts.report.stats["dynamic_safe_baseline_blocked_count"], 0)
        self.assertEqual(artifacts.report.stats["dynamic_review_only_count"], 0)
        self.assertEqual(len(artifacts.failures), 2)
        self.assertEqual(artifacts.failures[0].phase, "validate")
        self.assertIn("validate", artifacts.report.stats["phase_reason_code_counts"])
        self.assertIn("preflight", artifacts.report.stats["phase_reason_code_counts"])
        self.assertEqual(artifacts.report.stats["verification"]["partial_count"], 1)
        self.assertNotIn("generated_at", artifacts.report.stats["verification"])
        self.assertIn("actionability", artifacts.report.stats)
        self.assertIn("top_actionable_sql", artifacts.report.stats)
        self.assertEqual(len(artifacts.report.stats["top_actionable_sql"]), 1)
        self.assertIn("priority", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("delivery_status", artifacts.report.stats["top_actionable_sql"][0])
        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["delivery_tier"], "READY_TO_APPLY")
        self.assertIn("summary", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("why_now", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("blocker_primary_code", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("evidence_availability", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("semantic_gate_status", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("semantic_confidence_upgraded", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("semantic_unupgraded_reason", artifacts.report.stats["top_actionable_sql"][0])
        self.assertIn("semantic_blocked_reason", artifacts.report.stats["top_actionable_sql"][0])
        self.assertGreaterEqual(len(artifacts.diagnostics_sql_outcomes), 1)
        self.assertGreaterEqual(len(artifacts.diagnostics_sql_artifacts), 1)
        sql_artifact = artifacts.diagnostics_sql_artifacts[0]
        self.assertEqual(sql_artifact["artifact_refs"]["report"], "overview/report.json")
        self.assertEqual(sql_artifact["artifact_refs"]["proposals"], "pipeline/optimize/optimization.proposals.jsonl")
        self.assertEqual(sql_artifact["artifact_refs"]["acceptance"], "pipeline/validate/acceptance.results.jsonl")
        self.assertEqual(sql_artifact["artifact_refs"]["patches"], "pipeline/patch_generate/patch.results.jsonl")
        self.assertEqual(sql_artifact["artifact_refs"]["verification"], "pipeline/verification/ledger.jsonl")
        self.assertIn("candidate_generation_diagnostics", sql_artifact["artifact_refs"])
        self.assertEqual(sql_artifact["blocker_family"], "READY")
        self.assertEqual(sql_artifact["aggregation_shape_family"], "NONE")
        self.assertEqual(sql_artifact["aggregation_constraint_family"], "NONE")
        self.assertIsNone(sql_artifact["dynamic_baseline_family"])
        self.assertIsNone(sql_artifact["dynamic_delivery_class"])
        self.assertIn("top_blockers", artifacts.diagnostics_blockers_summary)
        self.assertIn("authoritative", artifacts.run_index)
        self.assertIn("integrity", artifacts.run_index)
        self.assertIn("status", artifacts.run_index["integrity"])
        self.assertIn("warning_codes", artifacts.run_index["integrity"])
        self.assertTrue(artifacts.run_index["integrity"]["sql_key_alignment_ok"])
        self.assertEqual(artifacts.run_index["groups"]["sql"]["catalog"], "sql/catalog.jsonl")
        self.assertIn("pipeline/scan/sqlunits.jsonl", artifacts.run_index["groups"]["pipeline"])
        self.assertIn("pipeline/optimize/optimization.proposals.jsonl", artifacts.run_index["groups"]["pipeline"])
        self.assertEqual(artifacts.report.evidence_confidence, "MEDIUM")
        self.assertIsNone(artifacts.report.validation_warnings)
        self.assertEqual(artifacts.verification_summary["coverage_by_phase"]["validate"]["ratio"], 1.0)
        self.assertEqual(artifacts.topology.runtime_policy["stage_timeout_ms"]["report"], 300)
        self.assertEqual(artifacts.health.report_json, str(Path(td) / "overview" / "report.json"))
        self.assertEqual(artifacts.sql_rows[0]["semantic_gate_status"], "UNCERTAIN")
        self.assertIn("semantic_confidence_upgraded", artifacts.sql_rows[0])
        self.assertIn("semantic_unupgraded_reason", artifacts.sql_rows[0])
        self.assertIn("semantic_blocked_reason", artifacts.sql_rows[0])

    def test_build_report_artifacts_counts_semantic_recovery_and_include_auto_materialization(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.countUser#v2"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.countUser#v2",
                    "status": "PASS",
                    "equivalence": {"checked": True},
                    "perfComparison": {"reasonCodes": []},
                    "securityChecks": {"dollar_substitution_removed": True},
                    "semanticEquivalence": {
                        "status": "PASS",
                        "confidence": "HIGH",
                        "equivalenceOverrideApplied": True,
                        "equivalenceOverrideRule": "SEMANTIC_KNOWN_EQUIVALENCE_COUNT_STAR_ONE",
                    },
                    "rewriteMaterialization": {
                        "mode": "FRAGMENT_TEMPLATE_SAFE_AUTO",
                        "reasonCode": "STATIC_FRAGMENT_SAFE",
                    },
                    "selectedPatchStrategy": {
                        "strategyType": "SAFE_WRAPPER_COLLAPSE",
                        "mode": "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
                    },
                    "canonicalization": {
                        "preferred": True,
                        "ruleId": "COUNT_CANONICAL_FORM",
                        "score": 27,
                        "reason": "count(*) is preferred as canonical count form",
                    },
                    "riskFlags": [],
                }
            ],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_recovery_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["semantic_false_block_recovered_count"], 1)
        self.assertEqual(artifacts.report.stats["include_safe_materialized_count"], 1)
        self.assertEqual(artifacts.report.stats["wrapper_collapse_recovered_count"], 1)
        self.assertEqual(artifacts.report.stats["patch_strategy_counts"]["SAFE_WRAPPER_COLLAPSE"], 1)
        self.assertEqual(artifacts.report.stats["canonical_rule_match_counts"]["COUNT_CANONICAL_FORM"], 1)
        self.assertEqual(artifacts.report.stats["canonical_preference_applied_count"], 1)
        self.assertEqual(artifacts.report.stats["aggregation_shape_counts"], {})
        self.assertEqual(artifacts.report.stats["aggregation_constraint_counts"], {})
        self.assertEqual(artifacts.report.stats["aggregation_safe_baseline_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_baseline_family_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_delivery_class_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_ready_baseline_family_counts"], {})
        self.assertEqual(artifacts.report.stats["dynamic_ready_patch_count"], 0)
        self.assertEqual(artifacts.report.stats["dynamic_safe_baseline_blocked_count"], 0)
        self.assertEqual(artifacts.report.stats["dynamic_review_only_count"], 0)

    def test_build_report_artifacts_counts_candidate_recovery_stats(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.cte#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.cte#v1",
                    "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT id FROM users", "rewriteStrategy": "INLINE_SIMPLE_CTE_RECOVERED"}],
                    "candidateGenerationDiagnostics": {
                        "degradationKind": "EMPTY_CANDIDATES",
                        "recoveryAttempted": True,
                        "recoveryStrategy": "INLINE_SIMPLE_CTE_RECOVERED",
                        "recoverySucceeded": True,
                        "recoveryReason": "SAFE_BASELINE_SHAPE_RECOVERY",
                    },
                }
            ],
            acceptance=[],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_candidate_recovery_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["candidate_degradation_counts"], {"EMPTY_CANDIDATES": 1})
        self.assertEqual(artifacts.report.stats["candidate_recovery_counts"], {"INLINE_SIMPLE_CTE_RECOVERED": 1})
        self.assertEqual(artifacts.report.stats["low_value_pruned_count"], 0)
        self.assertEqual(artifacts.report.stats["low_value_replaced_count"], 0)
        self.assertEqual(artifacts.report.stats["empty_candidate_recovered_count"], 1)
        self.assertEqual(artifacts.report.stats["empty_candidate_blocked_reason_counts"], {})
        self.assertEqual(artifacts.report.stats["text_fallback_recovered_count"], 0)

    def test_build_report_artifacts_tracks_blocked_empty_candidate_reasons(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.order.window#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.order.window#v1",
                    "candidateGenerationDiagnostics": {
                        "degradationKind": "EMPTY_CANDIDATES",
                        "recoveryAttempted": True,
                        "recoveryStrategy": None,
                        "recoverySucceeded": False,
                        "recoveryReason": "NO_SAFE_BASELINE_WINDOW",
                        "prunedLowValueCount": 0,
                    },
                }
            ],
            acceptance=[],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"report": 300},
                "stage_retry_max": {"report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_candidate_blocked_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["empty_candidate_blocked_reason_counts"], {"NO_SAFE_BASELINE_WINDOW": 1})

    def test_build_report_artifacts_counts_dynamic_strategy_from_patch_results(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14"}],
            proposals=[],
            acceptance=[
                {
                    "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14",
                    "status": "PASS",
                    "equivalence": {"checked": True},
                    "perfComparison": {"reasonCodes": []},
                    "securityChecks": {"dollar_substitution_removed": True},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                    "dynamicTemplate": {
                        "present": True,
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "capabilityTier": "SAFE_BASELINE",
                        "patchSurface": "STATEMENT_BODY",
                        "blockingReason": None,
                    },
                    "rewriteFacts": {
                        "dynamicTemplate": {
                            "present": True,
                            "capabilityProfile": {
                                "shapeFamily": "STATIC_INCLUDE_ONLY",
                                "capabilityTier": "SAFE_BASELINE",
                                "patchSurface": "STATEMENT_BODY",
                            },
                        },
                        "aggregationQuery": {
                            "capabilityProfile": {
                                "shapeFamily": "NONE",
                                "capabilityTier": "NONE",
                                "constraintFamily": "NONE",
                            }
                        },
                    },
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14",
                    "statementKey": "demo.user.advanced.listUsersViaStaticIncludeWrapped",
                    "applicable": True,
                    "strategyType": "DYNAMIC_STATEMENT_TEMPLATE_EDIT",
                    "dynamicTemplateStrategy": "DYNAMIC_STATEMENT_TEMPLATE_EDIT",
                    "deliveryOutcome": {"tier": "READY_TO_APPLY", "summary": "patch is ready to apply"},
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"report": 300},
                "stage_retry_max": {"report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_dynamic_strategy_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["patch_strategy_counts"]["DYNAMIC_STATEMENT_TEMPLATE_EDIT"], 1)

    def test_build_report_artifacts_tracks_aggregation_profiles(self) -> None:
        inputs = ReportInputs(
            units=[
                {"sqlKey": "demo.order.havingWrapped#v1"},
                {"sqlKey": "demo.user.distinct#v1"},
            ],
            proposals=[
                {
                    "sqlKey": "demo.user.distinct#v1",
                    "actionability": {
                        "score": 95,
                        "tier": "HIGH",
                        "autoPatchLikelihood": "LOW",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.order.havingWrapped#v1",
                    "status": "PASS",
                    "equivalence": {"checked": True},
                    "perfComparison": {"reasonCodes": []},
                    "securityChecks": {"dollar_substitution_removed": True},
                    "semanticEquivalence": {"status": "PASS", "confidence": "HIGH"},
                    "rewriteFacts": {
                        "aggregationQuery": {
                            "capabilityProfile": {
                                "shapeFamily": "HAVING",
                                "capabilityTier": "SAFE_BASELINE",
                                "constraintFamily": "SAFE_BASELINE",
                                "safeBaselineFamily": "REDUNDANT_HAVING_WRAPPER",
                            }
                        }
                    },
                    "selectedPatchStrategy": {"strategyType": "EXACT_TEMPLATE_EDIT"},
                    "riskFlags": [],
                },
                {
                    "sqlKey": "demo.user.distinct#v1",
                    "status": "FAIL",
                    "equivalence": {"checked": True},
                    "perfComparison": {"reasonCodes": []},
                    "securityChecks": {"dollar_substitution_removed": True},
                    "semanticEquivalence": {"status": "FAIL", "confidence": "HIGH"},
                    "patchability": {"eligible": False, "blockingReason": "AGGREGATION_CONSTRAINT:DISTINCT_RELAXATION"},
                    "rewriteFacts": {
                        "aggregationQuery": {
                            "capabilityProfile": {
                                "shapeFamily": "DISTINCT",
                                "capabilityTier": "REVIEW_REQUIRED",
                                "constraintFamily": "DISTINCT_RELAXATION",
                                "safeBaselineFamily": None,
                            }
                        }
                    },
                    "riskFlags": [],
                },
            ],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"report": 300},
                "stage_retry_max": {"report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_aggregation_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["aggregation_shape_counts"], {"HAVING": 1, "DISTINCT": 1})
        self.assertEqual(
            artifacts.report.stats["aggregation_constraint_counts"],
            {"SAFE_BASELINE": 1, "DISTINCT_RELAXATION": 1},
        )
        self.assertEqual(
            artifacts.report.stats["aggregation_safe_baseline_counts"],
            {"REDUNDANT_HAVING_WRAPPER": 1},
        )
        distinct_row = next(row for row in artifacts.diagnostics_sql_outcomes if row["sql_key"] == "demo.user.distinct#v1")
        self.assertEqual(distinct_row["aggregation_shape_family"], "DISTINCT")
        self.assertEqual(distinct_row["aggregation_constraint_family"], "DISTINCT_RELAXATION")
        self.assertIn("聚合语义", distinct_row["summary"])
        action_ids = [row["action_id"] for row in artifacts.report.summary.next_actions]
        self.assertIn("review-distinct-safety", action_ids)

    def test_build_report_artifacts_warns_on_optimize_db_explain_syntax_error(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findUsers#v1"}],
            proposals=[],
            acceptance=[],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.findUsers#v1",
                    "statement_key": "demo.user.findUsers",
                    "phase": "optimize",
                    "status": "PARTIAL",
                    "reason_code": "RISKY_DOLLAR_SUBSTITUTION",
                    "reason_message": "skip LLM for unsafe dollar substitution",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [
                        {
                            "name": "db_explain_syntax_ok",
                            "ok": False,
                            "severity": "warn",
                            "reason_code": "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR",
                            "detail": "You have an error in your SQL syntax near ILIKE",
                            "evidence_ref": None,
                        }
                    ],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_opt_warn_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertIsNotNone(artifacts.report.validation_warnings)
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", artifacts.report.validation_warnings[0])
        top_reason_codes = {row["reason_code"] for row in artifacts.report.stats["verification"]["top_reason_codes"]}
        self.assertIn("OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR", top_reason_codes)

    def test_action_plan_prefers_delivery_specific_guidance(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findIncluded#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "issues": [{"code": "SELECT_STAR"}],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 75,
                        "tier": "MEDIUM",
                        "autoPatchLikelihood": "MEDIUM",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "status": "PASS",
                    "deliveryReadiness": {"tier": "NEEDS_TEMPLATE_REWRITE"},
                    "perfComparison": {"reasonCodes": []},
                    "riskFlags": [],
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.findIncluded#v1",
                    "statementKey": "demo.user.findIncluded",
                    "applicable": None,
                    "deliveryOutcome": {
                        "tier": "PATCHABLE_WITH_REWRITE",
                        "summary": "patch can likely land after template-aware mapper refactoring",
                    },
                    "repairHints": [
                        {
                            "hintId": "expand-include",
                            "title": "Refactor include fragment path",
                            "command": None,
                        }
                    ],
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_actions_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.next_actions[0]["action_id"], "refactor-mapper")
        self.assertIn("模板", artifacts.next_actions[0]["reason"])

    def test_run_index_integrity_warns_when_validate_done_without_acceptance_ref(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.findUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.findUsers#v1",
                    "issues": [],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [],
                    "verdict": "NOOP",
                    "actionability": {"score": 10, "tier": "LOW", "autoPatchLikelihood": "LOW", "reasons": [], "blockedBy": []},
                }
            ],
            acceptance=[],
            patches=[],
            state=ReportStateSnapshot(
                phase_status={"optimize": "DONE", "validate": "DONE", "patch_generate": "DONE", "report": "DONE"},
                attempts_by_phase={"report": 1},
            ),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }
        with tempfile.TemporaryDirectory(prefix="report_builder_index_warn_") as td:
            artifacts = build_report_artifacts("run_demo_warn", "analyze", config, Path(td), inputs)

        integrity = artifacts.run_index["integrity"]
        self.assertEqual(integrity["status"], "WARN")
        self.assertIn("MISSING_ACCEPTANCE_REF", integrity["warning_codes"])
        self.assertIn("MISSING_PATCH_REF", integrity["warning_codes"])
        self.assertIn("MISSING_VERIFICATION_REF", integrity["warning_codes"])
        self.assertGreaterEqual(len(integrity["sql_ref_issues"]), 1)

    def test_action_plan_prefers_decision_layers_degraded_db_recheck(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 70,
                        "tier": "MEDIUM",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "NEED_MORE_PARAMS",
                    "perfComparison": {"reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                    "decisionLayers": {
                        "evidence": {"degraded": True, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"]},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "NEED_MORE_PARAMS", "feedbackReasonCode": "VALIDATE_PARAM_INSUFFICIENT"},
                    },
                }
            ],
            patches=[],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_decision_layers_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_degraded"], True)
        self.assertEqual(artifacts.next_actions[0]["action_id"], "check-db")

    def test_action_plan_prefers_evidence_review_for_critical_gap(self) -> None:
        inputs = ReportInputs(
            units=[{"sqlKey": "demo.user.listUsers#v1"}],
            proposals=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "issues": [],
                    "dbEvidenceSummary": {},
                    "planSummary": {},
                    "suggestions": [{"action": "PROJECT_COLUMNS", "sql": "SELECT id FROM users"}],
                    "verdict": "CAN_IMPROVE",
                    "actionability": {
                        "score": 85,
                        "tier": "HIGH",
                        "autoPatchLikelihood": "HIGH",
                        "reasons": [],
                        "blockedBy": [],
                    },
                }
            ],
            acceptance=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "status": "PASS",
                    "decisionLayers": {
                        "evidence": {"degraded": False, "reasonCodes": []},
                        "delivery": {"tier": "READY"},
                        "acceptance": {"status": "PASS"},
                    },
                }
            ],
            patches=[
                {
                    "sqlKey": "demo.user.listUsers#v1",
                    "statementKey": "demo.user.listUsers",
                    "applicable": True,
                }
            ],
            state=ReportStateSnapshot(phase_status={"report": "DONE"}, attempts_by_phase={"report": 1}),
            manifest_rows=[],
            verification_rows=[
                {
                    "run_id": "run_demo",
                    "sql_key": "demo.user.listUsers#v1",
                    "statement_key": "demo.user.listUsers",
                    "phase": "validate",
                    "status": "UNVERIFIED",
                    "reason_code": "VALIDATE_PASS_SELECTION_INCOMPLETE",
                    "reason_message": "missing evidence",
                    "evidence_refs": [],
                    "inputs": {},
                    "checks": [],
                    "verdict": {},
                    "created_at": "2026-03-03T00:00:00+00:00",
                }
            ],
        )
        config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }

        with tempfile.TemporaryDirectory(prefix="report_builder_critical_gap_") as td:
            artifacts = build_report_artifacts("run_demo", "analyze", config, Path(td), inputs)

        self.assertEqual(artifacts.report.stats["top_actionable_sql"][0]["evidence_state"], "CRITICAL_GAP")
        self.assertIn("缺失关键验证证据", artifacts.report.stats["top_actionable_sql"][0]["summary"])
        self.assertIn("缺失关键证据", artifacts.report.stats["top_actionable_sql"][0]["why_now"])
        self.assertEqual(artifacts.next_actions[0]["action_id"], "review-evidence")


if __name__ == "__main__":
    unittest.main()
