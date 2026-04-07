from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "convergence_snapshot.py"


class ConvergenceSnapshotScriptTest(unittest.TestCase):
    def test_convergence_snapshot_outputs_json_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_convergence_snapshot_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                json.dumps({"sqlKey": "demo.user.find", "status": "PASS", "semanticEquivalence": {"status": "PASS"}}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "statement_convergence.jsonl").write_text(
                json.dumps(
                    {
                        "statementKey": "demo.user.find",
                        "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                        "coverageLevel": "representative",
                        "sqlKeys": ["demo.user.find"],
                        "validateStatuses": {"pass": 1, "partial": 0, "fail": 0},
                        "semanticGate": {"passCount": 1, "blockedCount": 0, "uncertainCount": 0},
                        "convergenceDecision": "MANUAL_REVIEW",
                        "consensus": None,
                        "conflictReason": "PATCH_FAMILY_CONFLICT_OR_MISSING",
                        "evidenceRefs": [],
                        "generatedAt": "2026-04-06T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "patches.jsonl").write_text(
                json.dumps(
                    {
                        "sqlKey": "demo.user.find",
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

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(run_dir), "--format", "json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertIn("convergence_decision_counts", payload)
        self.assertEqual(payload["convergence_decision_counts"].get("MANUAL_REVIEW"), 1)
        self.assertEqual(payload["patch_convergence_blocked_count"], 1)


if __name__ == "__main__":
    unittest.main()
