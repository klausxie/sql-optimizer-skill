from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.devtools.harness.runtime import HarnessHooks, load_run_artifacts, prepare_fixture_project, run_until_complete
from sqlopt.devtools.harness.benchmark import BenchmarkSnapshot, compare_snapshots, snapshot_from_artifacts


def _write_cfg(td: str, project_root: Path, *, report_enabled: bool = True) -> Path:
    cfg = Path(td) / "sqlopt.benchmark.json"
    cfg.write_text(
        json.dumps(
            {
                "project": {"root_path": str(project_root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {
                    "platform": "postgresql",
                    "dsn": "postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
                },
                "report": {"enabled": report_enabled},
                "llm": {"enabled": False, "provider": "heuristic"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return cfg


class HarnessBenchmarkTest(unittest.TestCase):
    HOOKS = HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True})

    def test_snapshot_from_artifacts_extracts_stable_run_level_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_harness_benchmark_") as td:
            handle = prepare_fixture_project(Path(td), mutable=True, init_git=True)
            cfg = _write_cfg(td, handle.root_path, report_enabled=True)
            run_id = f"run_benchmark_{uuid4().hex[:8]}"
            result = run_until_complete(
                config_path=cfg,
                to_stage="patch_generate",
                run_id=run_id,
                repo_root=handle.root_path,
                hooks=self.HOOKS,
            )
            artifacts = load_run_artifacts(result.run_dir)
            snapshot = snapshot_from_artifacts(artifacts)

            self.assertEqual(snapshot.run_id, run_id)
            self.assertEqual(snapshot.status, "COMPLETED")
            self.assertEqual(snapshot.phase_status["report"], "DONE")
            self.assertGreaterEqual(snapshot.sql_total, 1)
            self.assertGreaterEqual(snapshot.blocked_total, 0)
            self.assertIsInstance(snapshot.blocker_family_counts, dict)
            self.assertIsInstance(snapshot.top_reason_codes, list)

    def test_compare_snapshots_returns_numeric_deltas_and_top_reason_changes(self) -> None:
        baseline = BenchmarkSnapshot(
            run_id="run_a",
            status="COMPLETED",
            verdict="PARTIAL",
            next_action="inspect",
            phase_status={"report": "DONE"},
            sql_total=10,
            proposal_total=6,
            accepted_total=4,
            patchable_total=2,
            patched_total=1,
            blocked_total=8,
            blocker_family_counts={"READY": 2, "SECURITY": 3},
            patch_strategy_counts={"EXACT_TEMPLATE_EDIT": 1},
            dynamic_delivery_class_counts={"READY_DYNAMIC_PATCH": 1},
            top_reason_codes=[{"code": "A", "count": 3}, {"code": "B", "count": 1}],
        )
        candidate = BenchmarkSnapshot(
            run_id="run_b",
            status="COMPLETED",
            verdict="PASS",
            next_action="apply",
            phase_status={"report": "DONE"},
            sql_total=10,
            proposal_total=7,
            accepted_total=6,
            patchable_total=4,
            patched_total=3,
            blocked_total=4,
            blocker_family_counts={"READY": 4, "SECURITY": 1},
            patch_strategy_counts={"EXACT_TEMPLATE_EDIT": 3},
            dynamic_delivery_class_counts={"READY_DYNAMIC_PATCH": 2},
            top_reason_codes=[{"code": "A", "count": 1}, {"code": "C", "count": 2}],
        )

        delta = compare_snapshots(baseline, candidate)

        self.assertEqual(delta.sql_total_delta, 0)
        self.assertEqual(delta.proposal_total_delta, 1)
        self.assertEqual(delta.accepted_total_delta, 2)
        self.assertEqual(delta.patchable_total_delta, 2)
        self.assertEqual(delta.patched_total_delta, 2)
        self.assertEqual(delta.blocked_total_delta, -4)
        self.assertEqual(delta.blocker_family_count_deltas["READY"], 2)
        self.assertEqual(delta.blocker_family_count_deltas["SECURITY"], -2)
        self.assertEqual(delta.top_reason_code_deltas["A"], -2)
        self.assertEqual(delta.top_reason_code_deltas["B"], -1)
        self.assertEqual(delta.top_reason_code_deltas["C"], 2)


if __name__ == "__main__":
    unittest.main()
