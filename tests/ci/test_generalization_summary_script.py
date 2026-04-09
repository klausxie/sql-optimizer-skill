from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlopt.devtools.generalization_blocker_inventory import (
    BLOCKED_BOUNDARY_SQL_KEYS,
    LOW_VALUE_ONLY_CLUSTER,
    NO_SAFE_BASELINE_RECOVERY_CLUSTER,
    POST_BATCH7_SENTINELS,
    READY_SENTINEL_SQL_KEYS,
    SEMANTIC_ERROR_CLUSTER,
    UNSUPPORTED_STRATEGY_CLUSTER,
)
from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "generalization_summary.py"


def _write_run(run_dir: Path, rows: list[dict[str, object]], patch_rows: list[dict[str, object]]) -> None:
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "statement_convergence.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "patches.jsonl").write_text(
        "\n".join(json.dumps(row) for row in patch_rows) + "\n",
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "acceptance.jsonl").write_text("", encoding="utf-8")
    (run_dir / "control").mkdir(parents=True, exist_ok=True)


def _write_complete_batch_run(
    run_dir: Path,
    *,
    batch_name: str,
    rows: list[dict[str, object]],
    patch_rows: list[dict[str, object]],
    fill_conflict_reason: str = "FILLER_REASON",
) -> None:
    expected_statement_keys = tuple(GENERALIZATION_BATCH_SCOPE_SQL_KEYS[batch_name])
    row_by_statement = {
        str(row.get("statementKey") or "").strip(): row
        for row in rows
        if str(row.get("statementKey") or "").strip()
    }
    patch_by_statement = {
        str(row.get("statementKey") or "").strip(): row
        for row in patch_rows
        if str(row.get("statementKey") or "").strip()
    }

    completed_rows = list(rows)
    completed_patch_rows = list(patch_rows)
    for statement_key in expected_statement_keys:
        if statement_key not in row_by_statement:
            completed_rows.append(
                {
                    "statementKey": statement_key,
                    "shapeFamily": "UNKNOWN",
                    "coverageLevel": "representative",
                    "sqlKeys": [statement_key],
                    "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                    "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                    "convergenceDecision": "MANUAL_REVIEW",
                    "consensus": None,
                    "conflictReason": fill_conflict_reason,
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-08T00:00:00+00:00",
                }
            )
        if statement_key not in patch_by_statement:
            completed_patch_rows.append(
                {
                    "statementKey": statement_key,
                    "patchFiles": [],
                    "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                }
            )

    _write_run(run_dir, completed_rows, completed_patch_rows)


class GeneralizationSummaryScriptTest(unittest.TestCase):
    def test_blocker_inventory_matches_fresh_baseline(self) -> None:
        self.assertEqual(
            READY_SENTINEL_SQL_KEYS,
            (
                "demo.test.complex.fromClauseSubquery",
                "demo.user.countUser",
                "demo.test.complex.wrapperCount",
            ),
        )
        self.assertEqual(
            BLOCKED_BOUNDARY_SQL_KEYS,
            (
                "demo.order.harness.findOrdersByNos",
                "demo.shipment.harness.findShipmentsByOrderIds",
                "demo.test.complex.multiFragmentSeparate",
                "demo.test.complex.selectWithFragmentChoose",
            ),
        )
        self.assertEqual(
            LOW_VALUE_ONLY_CLUSTER,
            (
                "demo.order.harness.findOrdersByUserIdsAndStatus",
                "demo.order.harness.listOrdersWithUsersPaged",
                "demo.shipment.harness.findShipments",
                "demo.test.complex.chooseMultipleWhen",
                "demo.test.complex.inSubquery",
                "demo.test.complex.multiFragmentLevel1",
                "demo.test.complex.multiFragmentLevel2",
                "demo.test.complex.staticOrderBy",
                "demo.user.advanced.findUsersByKeyword",
            ),
        )
        self.assertEqual(
            NO_SAFE_BASELINE_RECOVERY_CLUSTER,
            (
                "demo.test.complex.includeSimple",
                "demo.test.complex.staticSimpleSelect",
            ),
        )
        self.assertEqual(
            SEMANTIC_ERROR_CLUSTER,
            (
                "demo.test.complex.chooseBasic",
                "demo.test.complex.chooseWithLimit",
                "demo.test.complex.fragmentMultiplePlaces",
            ),
        )
        self.assertEqual(
            UNSUPPORTED_STRATEGY_CLUSTER,
            (
                "demo.test.complex.existsSubquery",
                "demo.test.complex.leftJoinWithNull",
            ),
        )
        self.assertEqual(
            POST_BATCH7_SENTINELS,
            {
                "POST_BATCH7_CANDIDATE_TARGETS": (
                    "demo.user.advanced.findUsersByKeyword",
                ),
                "POST_BATCH7_SAFE_BASELINE_SENTINELS": (
                    "demo.shipment.harness.findShipments",
                ),
                "POST_BATCH7_SEMANTIC_SENTINELS": (
                    "demo.order.harness.listOrdersWithUsersPaged",
                    "demo.test.complex.chooseBasic",
                    "demo.test.complex.chooseMultipleWhen",
                ),
            },
        )

    def test_json_summary_combines_multiple_batches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch1_") as td1, tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch2_") as td2, tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch3_") as td3:
            run_dir1 = Path(td1)
            run_dir2 = Path(td2)
            run_dir3 = Path(td3)
            _write_complete_batch_run(
                run_dir1,
                batch_name="generalization-batch1",
                rows=[
                    {
                        "statementKey": "demo.user.findUsers",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.findUsers"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "VALIDATE_STATUS_NOT_PASS",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.user.countUser",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.countUser"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "AUTO_PATCHABLE",
                        "consensus": {"patchFamily": "STATIC_INCLUDE_WRAPPER_COLLAPSE", "patchSurface": "statement", "rewriteOpsFingerprint": "x"},
                        "conflictReason": None,
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.user.findUsers",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.user.countUser",
                        "patchFiles": ["demo.user.countUser.patch"],
                        "selectionReason": {"code": "PATCH_SELECTED"},
                    },
                ],
                fill_conflict_reason="NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            )
            _write_complete_batch_run(
                run_dir2,
                batch_name="generalization-batch2",
                rows=[
                    {
                        "statementKey": "demo.test.complex.wrapperCount",
                        "shapeFamily": "STATIC_SUBQUERY_WRAPPER",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.wrapperCount"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "AUTO_PATCHABLE",
                        "consensus": {"patchFamily": "STATIC_SUBQUERY_WRAPPER_COLLAPSE", "patchSurface": "statement", "rewriteOpsFingerprint": "x"},
                        "conflictReason": None,
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    }
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.test.complex.wrapperCount",
                        "patchFiles": ["demo.test.complex.wrapperCount.patch"],
                        "selectionReason": {"code": "PATCH_SELECTED"},
                    }
                ],
                fill_conflict_reason="FILLER_REASON",
            )
            _write_complete_batch_run(
                run_dir3,
                batch_name="generalization-batch3",
                rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.includeSimple"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "SOME_NEW_REASON",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    }
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    }
                ],
                fill_conflict_reason="FILLER_REASON",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch1={run_dir1}",
                    "--batch-run",
                    f"generalization-batch2={run_dir2}",
                    "--batch-run",
                    f"generalization-batch3={run_dir3}",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["batches"]), 3)
        self.assertEqual(payload["overall"]["total_statements"], 15)
        self.assertEqual(payload["overall"]["decision_counts"]["AUTO_PATCHABLE"], 2)
        self.assertEqual(payload["overall"]["decision_counts"]["MANUAL_REVIEW"], 13)
        self.assertAlmostEqual(payload["overall"]["auto_patchable_rate"], 2 / 15)
        self.assertEqual(payload["overall"]["blocked_statement_count"], 13)
        self.assertEqual(payload["overall"]["blocker_bucket_counts"]["VALIDATE_STATUS_NOT_PASS"], 1)
        self.assertEqual(payload["overall"]["blocker_bucket_counts"]["OTHER"], 9)
        self.assertEqual(payload["overall"]["ready_regressions"], 1)
        self.assertEqual(payload["overall"]["blocked_boundary_regressions"], 0)
        self.assertEqual(payload["overall"]["decision_focus"], "OTHER")
        self.assertEqual(payload["overall"]["recommended_next_step"], "inspect_misc_blockers")
        self.assertEqual(payload["overall"]["patch_convergence_blocked_count"], 13)

    def test_json_summary_batch7_only_exposes_stable_focus_and_sentinels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch7_") as td:
            run_dir = Path(td)
            _write_complete_batch_run(
                run_dir,
                batch_name="generalization-batch7",
                rows=[
                    {
                        "statementKey": "demo.order.harness.listOrdersWithUsersPaged",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.order.harness.listOrdersWithUsersPaged"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 0, "blockedCount": 1, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "NO_SAFE_BASELINE_RECOVERY",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-09T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.shipment.harness.findShipments",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.shipment.harness.findShipments"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 0, "blockedCount": 1, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "NO_SAFE_BASELINE_RECOVERY",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-09T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.user.advanced.findUsersByKeyword",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.advanced.findUsersByKeyword"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 0, "blockedCount": 1, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "NO_SAFE_BASELINE_RECOVERY",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-09T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.test.complex.chooseBasic",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.chooseBasic"],
                        "validateStatuses": {"pass": 0, "partial": 0, "fail": 1},
                        "semanticGate": {"passCount": 0, "blockedCount": 1, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "VALIDATE_SEMANTIC_ERROR",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-09T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.test.complex.chooseMultipleWhen",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.chooseMultipleWhen"],
                        "validateStatuses": {"pass": 0, "partial": 0, "fail": 1},
                        "semanticGate": {"passCount": 0, "blockedCount": 1, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "VALIDATE_SEMANTIC_ERROR",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-09T00:00:00+00:00",
                    },
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.order.harness.listOrdersWithUsersPaged",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.shipment.harness.findShipments",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.user.advanced.findUsersByKeyword",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.test.complex.chooseBasic",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.test.complex.chooseMultipleWhen",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch7={run_dir}",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(len(payload["batches"]), 1)

            batch = payload["batches"][0]
            self.assertEqual(batch["batch"], "generalization-batch7")
            self.assertEqual(batch["decision_focus"], "NO_PATCHABLE_CANDIDATE_SELECTED")
            self.assertEqual(batch["recommended_next_step"], "fix_shared_candidate_selection_gaps")
            self.assertEqual(batch["ready_regressions"], 0)
            self.assertEqual(batch["blocked_boundary_regressions"], 0)
            self.assertEqual(
                batch["post_batch7_sentinels"],
                {
                    group_name: list(sql_keys)
                    for group_name, sql_keys in POST_BATCH7_SENTINELS.items()
                },
            )

            self.assertEqual(payload["overall"]["decision_focus"], "NO_PATCHABLE_CANDIDATE_SELECTED")
            self.assertEqual(payload["overall"]["recommended_next_step"], "fix_shared_candidate_selection_gaps")
            self.assertEqual(payload["overall"]["ready_regressions"], 0)
            self.assertEqual(payload["overall"]["blocked_boundary_regressions"], 0)

            text_proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch7={run_dir}",
                    "--format",
                    "text",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(text_proc.returncode, 0, text_proc.stderr or text_proc.stdout)
            self.assertIn("ready_regressions=0", text_proc.stdout)
            self.assertIn("blocked_boundary_regressions=0", text_proc.stdout)
            self.assertIn("decision_focus=NO_PATCHABLE_CANDIDATE_SELECTED", text_proc.stdout)
            self.assertIn("recommended_next_step=fix_shared_candidate_selection_gaps", text_proc.stdout)

    def test_text_summary_lists_statement_outcomes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch3_") as td:
            run_dir = Path(td)
            _write_complete_batch_run(
                run_dir,
                batch_name="generalization-batch3",
                rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.includeSimple"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "SOME_NEW_REASON",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    }
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    }
                ],
                fill_conflict_reason="NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch3={run_dir}",
                    "--format",
                    "text",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("batch=generalization-batch3", proc.stdout)
        self.assertIn("total_statements=5", proc.stdout)
        self.assertIn("statement=demo.test.complex.includeSimple decision=MANUAL_REVIEW", proc.stdout)
        self.assertIn("top_conflict_reasons=NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY:4,SOME_NEW_REASON:1", proc.stdout)
        self.assertIn("auto_patchable_rate=0.0000", proc.stdout)
        self.assertIn("blocked_statement_count=5", proc.stdout)
        self.assertIn("blocker_bucket_counts={'NO_PATCHABLE_CANDIDATE_SELECTED': 4, 'SEMANTIC_GATE_NOT_PASS': 0, 'VALIDATE_STATUS_NOT_PASS': 0, 'SHAPE_FAMILY_NOT_TARGET': 0, 'OTHER': 1}", proc.stdout)
        self.assertIn("ready_regressions=0", proc.stdout)
        self.assertIn("blocked_boundary_regressions=0", proc.stdout)
        self.assertIn("decision_focus=NO_PATCHABLE_CANDIDATE_SELECTED", proc.stdout)
        self.assertIn("recommended_next_step=fix_shared_candidate_selection_gaps", proc.stdout)

    def test_bucket_grouping_keeps_specific_no_candidate_reasons_under_shared_focus(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch3_") as td:
            run_dir = Path(td)
            _write_complete_batch_run(
                run_dir,
                batch_name="generalization-batch3",
                rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.includeSimple"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "NO_SAFE_BASELINE_RECOVERY",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.test.complex.staticOrderBy",
                        "shapeFamily": "STATIC_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.test.complex.staticOrderBy"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.test.complex.includeSimple",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.test.complex.staticOrderBy",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                ],
                fill_conflict_reason="NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch3={run_dir}",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["overall"]["blocker_bucket_counts"]["NO_PATCHABLE_CANDIDATE_SELECTED"], 5)
        self.assertEqual(payload["overall"]["decision_focus"], "NO_PATCHABLE_CANDIDATE_SELECTED")

    def test_bucket_grouping_maps_specific_validate_and_semantic_reasons(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch1_") as td:
            run_dir = Path(td)
            _write_complete_batch_run(
                run_dir,
                batch_name="generalization-batch1",
                rows=[
                    {
                        "statementKey": "demo.user.findUsers",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.findUsers"],
                        "validateStatuses": {"pass": 0, "partial": 1, "fail": 0},
                        "semanticGate": {"passCount": 0, "blockedCount": 0, "uncertainCount": 1},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                    {
                        "statementKey": "demo.order.harness.listOrdersWithUsersPaged",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.order.harness.listOrdersWithUsersPaged"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 0, "blockedCount": 0, "uncertainCount": 1},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "SEMANTIC_PREDICATE_CHANGED",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    },
                ],
                patch_rows=[
                    {
                        "statementKey": "demo.user.findUsers",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                    {
                        "statementKey": "demo.order.harness.listOrdersWithUsersPaged",
                        "patchFiles": [],
                        "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                    },
                ],
                fill_conflict_reason="FILLER_REASON",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch1={run_dir}",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["overall"]["blocker_bucket_counts"]["VALIDATE_STATUS_NOT_PASS"], 1)
        self.assertEqual(payload["overall"]["blocker_bucket_counts"]["SEMANTIC_GATE_NOT_PASS"], 1)

    def test_missing_batch_run_directory_fails(self) -> None:
        missing_run_dir = ROOT / "tests" / "fixtures" / "projects" / "sample_project" / "runs" / "run_does_not_exist"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--batch-run",
                f"generalization-batch1={missing_run_dir}",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("does not exist", proc.stderr)

    def test_missing_expected_statement_fails_instead_of_reporting_false_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_generalization_batch1_partial_") as td:
            run_dir = Path(td)
            _write_run(
                run_dir,
                [
                    {
                        "statementKey": "demo.user.countUser",
                        "shapeFamily": "STATIC_INCLUDE_ONLY",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.countUser"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "AUTO_PATCHABLE",
                        "consensus": {
                            "patchFamily": "STATIC_INCLUDE_WRAPPER_COLLAPSE",
                            "patchSurface": "statement",
                            "rewriteOpsFingerprint": "x",
                        },
                        "conflictReason": None,
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-08T00:00:00+00:00",
                    }
                ],
                [
                    {
                        "statementKey": "demo.user.countUser",
                        "patchFiles": ["demo.user.countUser.patch"],
                        "selectionReason": {"code": "PATCH_SELECTED"},
                    }
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--batch-run",
                    f"generalization-batch1={run_dir}",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("missing expected statements", proc.stderr)
        self.assertIn("demo.test.complex.fromClauseSubquery", proc.stderr)
        self.assertIn("demo.user.findUsers", proc.stderr)


if __name__ == "__main__":
    unittest.main()
