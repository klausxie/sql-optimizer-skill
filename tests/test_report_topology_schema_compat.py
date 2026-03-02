from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlopt.contracts import ContractValidator
from sqlopt.stages import report as report_stage

ROOT = Path(__file__).resolve().parents[1]


class ReportTopologySchemaCompatTest(unittest.TestCase):
    def test_topology_runtime_policy_excludes_preflight_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_report_topology_") as td:
            run_dir = Path(td)
            (run_dir / "proposals").mkdir(parents=True, exist_ok=True)
            (run_dir / "acceptance").mkdir(parents=True, exist_ok=True)
            (run_dir / "patches").mkdir(parents=True, exist_ok=True)
            (run_dir / "ops").mkdir(parents=True, exist_ok=True)
            (run_dir / "scan.sqlunits.jsonl").write_text("", encoding="utf-8")
            (run_dir / "proposals" / "optimization.proposals.jsonl").write_text("", encoding="utf-8")
            (run_dir / "acceptance" / "acceptance.results.jsonl").write_text("", encoding="utf-8")
            (run_dir / "patches" / "patch.results.jsonl").write_text("", encoding="utf-8")
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
            report_stage.generate("rpt_topology", "analyze", config, run_dir, validator)
            topology = json.loads((run_dir / "ops" / "topology.json").read_text(encoding="utf-8"))
            timeout_keys = set((topology.get("runtime_policy") or {}).get("stage_timeout_ms", {}).keys())
            retry_keys = set((topology.get("runtime_policy") or {}).get("stage_retry_max", {}).keys())
            self.assertNotIn("preflight", timeout_keys)
            self.assertNotIn("preflight", retry_keys)
            self.assertEqual(timeout_keys, {"scan", "optimize", "validate", "apply", "report"})
            self.assertEqual(retry_keys, {"scan", "optimize", "validate", "apply", "report"})


if __name__ == "__main__":
    unittest.main()
