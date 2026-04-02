from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.stages import report as report_stage

ROOT = Path(__file__).resolve().parents[2]


class ReportTopologySchemaCompatTest(unittest.TestCase):
    def test_report_contract_stays_minimal_and_excludes_runtime_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_topology_") as td:
            run_dir = Path(td)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "scan.jsonl").write_text("", encoding="utf-8")
            (run_dir / "artifacts" / "proposals.jsonl").write_text("", encoding="utf-8")
            (run_dir / "artifacts" / "acceptance.jsonl").write_text("", encoding="utf-8")
            (run_dir / "artifacts" / "patches.jsonl").write_text("", encoding="utf-8")
            (run_dir / "control" / "manifest.jsonl").write_text("", encoding="utf-8")
            config = {
                "policy": {
                    "require_perf_improvement": False,
                    "cost_threshold_pct": 0,
                    "allow_seq_scan_if_rows_below": 0,
                    "semantic_strict_mode": True,
                },
                "runtime": {
                    "stage_timeout_ms": {"preflight": 1, "scan": 1, "optimize": 1, "validate": 1, "apply": 1, "report": 1},
                    "stage_retry_max": {"preflight": 0, "scan": 0, "optimize": 0, "validate": 0, "apply": 0, "report": 0},
                    "stage_retry_backoff_ms": 1,
                },
                "llm": {"enabled": False},
            }
            validator = ContractValidator(ROOT)
            report = report_stage.generate("rpt_topology", "analyze", config, run_dir, validator)
            self.assertEqual(
                set(report.keys()),
                {
                    "run_id",
                    "generated_at",
                    "status",
                    "verdict",
                    "next_action",
                    "phase_status",
                },
            )
            self.assertNotIn("runtime_policy", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
