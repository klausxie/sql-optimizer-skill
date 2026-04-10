from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "boundary_gate.py"


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


class BoundaryGateScriptTest(unittest.TestCase):
    def _prepare_batch13_run(self, *, provider_limited: bool = True, ready_regression: bool = False) -> Path:
        temp_dir = tempfile.TemporaryDirectory(prefix="sqlopt_boundary_gate_")
        self.addCleanup(temp_dir.cleanup)
        run_dir = Path(temp_dir.name)
        _write_run(
            run_dir,
            [
                {
                    "statementKey": "demo.test.complex.fromClauseSubquery",
                    "shapeFamily": "STATIC_STATEMENT",
                    "coverageLevel": "representative",
                    "sqlKeys": ["demo.test.complex.fromClauseSubquery"],
                    "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                    "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                    "convergenceDecision": "MANUAL_REVIEW" if ready_regression else "AUTO_PATCHABLE",
                    "consensus": None if ready_regression else {"patchFamily": "STATIC_WRAPPER_COLLAPSE"},
                    "conflictReason": "NO_SAFE_BASELINE_GROUP_BY" if ready_regression else None,
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
                },
                {
                    "statementKey": "demo.user.advanced.findUsersByKeyword",
                    "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                    "coverageLevel": "representative",
                    "sqlKeys": ["demo.user.advanced.findUsersByKeyword"],
                    "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                    "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                    "convergenceDecision": "MANUAL_REVIEW",
                    "consensus": None,
                    "conflictReason": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY" if provider_limited else "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER",
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
                },
                {
                    "statementKey": "demo.test.complex.multiFragmentLevel1",
                    "shapeFamily": "MULTI_FRAGMENT_INCLUDE",
                    "coverageLevel": "representative",
                    "sqlKeys": ["demo.test.complex.multiFragmentLevel1"],
                    "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                    "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                    "convergenceDecision": "MANUAL_REVIEW",
                    "consensus": None,
                    "conflictReason": "NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE",
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
                },
                {
                    "statementKey": "demo.test.complex.includeNested",
                    "shapeFamily": "STATIC_INCLUDE_ONLY",
                    "coverageLevel": "representative",
                    "sqlKeys": ["demo.test.complex.includeNested"],
                    "validateStatuses": {"pass": 0, "partial": 1, "fail": 0},
                    "semanticGate": {"passCount": 0, "blockedCount": 0, "uncertainCount": 1},
                    "convergenceDecision": "MANUAL_REVIEW",
                    "consensus": None,
                    "conflictReason": "VALIDATE_SEMANTIC_ROW_COUNT_ERROR",
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
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
                    "conflictReason": "SEMANTIC_PREDICATE_CONJUNCT_REMOVED",
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
                },
            ],
            [
                {
                    "statementKey": "demo.user.advanced.findUsersByKeyword",
                    "patchFiles": [],
                    "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                }
            ],
        )
        return run_dir

    def _prepare_batch1_ready_regression_run(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory(prefix="sqlopt_boundary_gate_batch1_")
        self.addCleanup(temp_dir.cleanup)
        run_dir = Path(temp_dir.name)
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
                    "convergenceDecision": "MANUAL_REVIEW",
                    "consensus": None,
                    "conflictReason": "NO_SAFE_BASELINE_GROUP_BY",
                    "evidenceRefs": [],
                    "generatedAt": "2026-04-10T00:00:00+00:00",
                }
            ],
            [
                {
                    "statementKey": "demo.user.countUser",
                    "patchFiles": [],
                    "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED"},
                }
            ],
        )
        return run_dir

    def test_observe_mode_reports_gate_pass_and_boundary_categories(self) -> None:
        run_dir = self._prepare_batch13_run()
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--batch-run",
                f"generalization-batch13={run_dir}",
                "--mode",
                "observe",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["gate_passed"])
        self.assertEqual(payload["overall"]["ready_regressions"], 0)
        self.assertEqual(payload["overall"]["blocked_boundary_regressions"], 0)
        self.assertEqual(
            payload["checked_boundary_categories"]["demo.user.advanced.findUsersByKeyword"],
            "PROVIDER_LIMITED",
        )

    def test_hard_mode_fails_on_ready_regression(self) -> None:
        run_dir = self._prepare_batch1_ready_regression_run()
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--batch-run",
                f"generalization-batch1={run_dir}",
                "--mode",
                "hard",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["gate_passed"])

    def test_hard_mode_fails_on_boundary_category_drift(self) -> None:
        run_dir = self._prepare_batch13_run(provider_limited=False)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--batch-run",
                f"generalization-batch13={run_dir}",
                "--mode",
                "hard",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["gate_passed"])
        self.assertIn("demo.user.advanced.findUsersByKeyword", payload["boundary_category_mismatches"])


if __name__ == "__main__":
    unittest.main()
