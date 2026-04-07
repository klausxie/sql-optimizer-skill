from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "if_guarded_progress.py"


class IfGuardedProgressScriptTest(unittest.TestCase):
    def _prepare_run_dir(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory(prefix="sqlopt_if_guarded_progress_")
        self.addCleanup(temp_dir.cleanup)
        run_dir = Path(temp_dir.name)
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts" / "statement_convergence.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "statementKey": "demo.user.findA",
                            "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                            "coverageLevel": "representative",
                            "sqlKeys": ["demo.user.findA"],
                            "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                            "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                            "convergenceDecision": "AUTO_PATCHABLE",
                            "consensus": {"patchFamily": "X", "patchSurface": "statement", "rewriteOpsFingerprint": "o1"},
                            "conflictReason": None,
                            "evidenceRefs": [],
                            "generatedAt": "2026-04-06T00:00:00+00:00",
                        }
                    ),
                    json.dumps(
                        {
                            "statementKey": "demo.user.findB",
                            "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                            "coverageLevel": "representative",
                            "sqlKeys": ["demo.user.findB"],
                            "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                            "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                            "convergenceDecision": "MANUAL_REVIEW",
                            "consensus": None,
                            "conflictReason": "PATCH_FAMILY_CONFLICT_OR_MISSING",
                            "evidenceRefs": [],
                            "generatedAt": "2026-04-06T00:00:00+00:00",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "artifacts" / "patches.jsonl").write_text(
            json.dumps(
                {
                    "sqlKey": "demo.user.findB",
                    "statementKey": "demo.user.findB",
                    "patchFiles": [],
                    "diffSummary": {"skipped": True, "changed": False},
                    "applyMode": "PATCH_ONLY",
                    "rollback": "not_applied",
                    "selectionReason": {"code": "PATCH_CONVERGENCE_REVIEW_REQUIRED", "message": "blocked"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return run_dir

    def test_observe_mode_outputs_progress_json(self) -> None:
        run_dir = self._prepare_run_dir()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(run_dir), "--mode", "observe", "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["total_statements"], 2)
        self.assertEqual(payload["decision_counts"]["AUTO_PATCHABLE"], 1)
        self.assertEqual(payload["decision_counts"]["MANUAL_REVIEW"], 1)
        self.assertEqual(payload["patch_convergence_blocked_count"], 1)

    def test_hard_mode_fails_when_rate_below_threshold(self) -> None:
        run_dir = self._prepare_run_dir()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(run_dir), "--mode", "hard", "--min-auto-rate", "0.8", "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["gate_passed"])

    def test_text_format_outputs_stable_human_summary(self) -> None:
        run_dir = self._prepare_run_dir()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(run_dir), "--mode", "observe", "--format", "text"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        lines = proc.stdout.strip().splitlines()
        self.assertIn("shape_family=IF_GUARDED_FILTER_STATEMENT", lines)
        self.assertIn("total_statements=2", lines)
        self.assertIn("auto_patchable_rate=0.5000", lines)
        self.assertIn("patch_convergence_blocked_count=1", lines)
        self.assertIn("top_conflict_reasons=PATCH_FAMILY_CONFLICT_OR_MISSING:1", lines)


if __name__ == "__main__":
    unittest.main()
