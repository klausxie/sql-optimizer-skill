from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SchemaValidateAllScriptTest(unittest.TestCase):
    def test_validates_current_run_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_schema_validate_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            for rel in (
                "artifacts/scan.jsonl",
                "artifacts/fragments.jsonl",
                "artifacts/proposals.jsonl",
                "artifacts/acceptance.jsonl",
                "artifacts/patches.jsonl",
            ):
                (run_dir / rel).write_text("", encoding="utf-8")
            (run_dir / "report.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_demo",
                        "generated_at": "2026-04-01T00:00:00+00:00",
                        "target_stage": "report",
                        "status": "DONE",
                        "verdict": "PASS",
                        "next_action": "none",
                        "phase_status": {
                            "scan": "DONE",
                            "optimize": "DONE",
                            "validate": "DONE",
                            "patch_generate": "DONE",
                            "report": "DONE",
                        },
                        "stats": {
                            "sql_total": 0,
                            "proposal_total": 0,
                            "accepted_total": 0,
                            "patchable_total": 0,
                            "patched_total": 0,
                            "blocked_total": 0,
                        },
                        "blockers": {"top_reason_codes": []},
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "schema_validate_all.py"), str(run_dir)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual(proc.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()
