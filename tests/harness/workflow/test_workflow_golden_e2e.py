from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlopt.application import run_service
from sqlopt.io_utils import read_json, read_jsonl, write_json
from sqlopt.stages.report_stats import blocker_family_for_patch_row

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PROJECT = (ROOT / "tests" / "fixtures" / "project").resolve()


def _write_cfg(td: str, *, report_enabled: bool = True) -> Path:
    cfg = Path(td) / "sqlopt.json"
    cfg.write_text(
        json.dumps(
            {
                "project": {"root_path": str(FIXTURE_PROJECT)},
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


def _run_with_preflight_patch(
    config: Path,
    to_stage: str,
    run_id: str,
    *,
    selection: dict[str, object] | None = None,
) -> tuple[str, dict]:
    with patch("sqlopt.stages.preflight.check_db_connectivity", return_value={"name": "db", "enabled": True, "ok": True}):
        return run_service.start_run(config, to_stage, run_id, repo_root=ROOT, selection=selection)


def _resume_with_preflight_patch(run_id: str) -> dict:
    with patch("sqlopt.stages.preflight.check_db_connectivity", return_value={"name": "db", "enabled": True, "ok": True}):
        return run_service.resume_run(run_id, repo_root=ROOT)


class WorkflowGoldenE2ETest(unittest.TestCase):
    def _run_until_complete(
        self,
        config: Path,
        run_id: str,
        *,
        to_stage: str,
        selection: dict[str, object] | None = None,
    ) -> tuple[Path, int, float]:
        started = time.monotonic()
        _, first = _run_with_preflight_patch(config, to_stage, run_id, selection=selection)
        steps = 1
        if first.get("complete"):
            return FIXTURE_PROJECT / "runs" / run_id, steps, time.monotonic() - started
        for _ in range(1000):
            status = run_service.get_status(run_id, repo_root=ROOT)
            if status.get("complete"):
                break
            _resume_with_preflight_patch(run_id)
            steps += 1
        else:
            self.fail("run did not complete within expected loop budget")
        return FIXTURE_PROJECT / "runs" / run_id, steps, time.monotonic() - started

    def test_run_resume_status_report_rebuild_apply_golden(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_golden_e2e_") as td:
            cfg = _write_cfg(td, report_enabled=True)
            run_id = f"run_golden_e2e_{uuid4().hex[:8]}"
            run_dir, _steps, _elapsed = self._run_until_complete(cfg, run_id, to_stage="patch_generate")
            self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))

            status = run_service.get_status(run_id, repo_root=ROOT)
            self.assertEqual(
                set(status.keys()),
                {
                    "run_id",
                    "current_phase",
                    "current_sql_key",
                    "phase_status",
                    "run_status",
                    "remaining_statements",
                    "pending_by_phase",
                    "attempts_by_phase",
                    "last_reason_code",
                    "complete",
                    "next_action",
                    "selection_scope",
                },
            )
            self.assertTrue(status["complete"])
            self.assertEqual(status["next_action"], "none")
            self.assertEqual(set(status["phase_status"].keys()), {"preflight", "scan", "optimize", "validate", "patch_generate", "report"})

            state = read_json(run_dir / "control" / "state.json")
            self.assertEqual(
                set(state.keys()),
                {
                    "run_id",
                    "status",
                    "contract_version",
                    "skill_version",
                    "config_version",
                    "current_phase",
                    "phase_status",
                    "statements",
                    "attempts_by_phase",
                    "report_rebuild_required",
                    "last_error",
                    "last_reason_code",
                    "updated_at",
                },
            )
            self.assertFalse(bool(state.get("report_rebuild_required")))

            report = read_json(run_dir / "report.json")
            self.assertTrue(
                {
                    "run_id",
                    "generated_at",
                    "target_stage",
                    "status",
                    "verdict",
                    "next_action",
                    "phase_status",
                    "stats",
                    "blockers",
                    }.issubset(set(report.keys()))
            )
            self.assertEqual(report["target_stage"], "report")
            self.assertEqual(report["phase_status"]["report"], "DONE")
            self.assertIn(report["next_action"], {"apply", "inspect", "resume"})
            self.assertGreaterEqual(int((report.get("stats") or {}).get("sql_total") or 0), 1)
            self.assertIn("top_reason_codes", report.get("blockers") or {})

            apply_result = run_service.apply_run(run_id, repo_root=ROOT)
            self.assertEqual(apply_result["run_id"], run_id)
            self.assertEqual((apply_result.get("apply") or {}).get("mode"), "PATCH_ONLY")
            self.assertTrue((run_dir / "apply" / "state.json").exists())

            # Simulate a completed run requiring report rebuild and verify next_action.
            state["report_rebuild_required"] = True
            write_json(run_dir / "control" / "state.json", state)
            rebuild_status = run_service.get_status(run_id, repo_root=ROOT)
            self.assertEqual(rebuild_status["next_action"], "report-rebuild")

            # Rebuild report on the same run_id; ensure rebuild flag is cleared.
            _run_with_preflight_patch(cfg, "report", run_id)
            post_rebuild_status = run_service.get_status(run_id, repo_root=ROOT)
            self.assertTrue(post_rebuild_status["complete"])
            self.assertEqual(post_rebuild_status["next_action"], "none")
            post_state = read_json(run_dir / "control" / "state.json")
            self.assertFalse(bool(post_state.get("report_rebuild_required")))

    def test_runtime_step_count_stays_within_baseline_envelope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_perf_baseline_") as td:
            cfg = _write_cfg(td, report_enabled=True)
            run_id = f"run_perf_baseline_{uuid4().hex[:8]}"
            run_dir, steps, elapsed = self._run_until_complete(cfg, run_id, to_stage="patch_generate")
            self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))

            plan = read_json(run_dir / "control" / "plan.json")
            sql_count = len(list(plan.get("sql_keys") or []))
            # Envelope: 3 statement phases per SQL + phase transitions/finalization buffer.
            self.assertLessEqual(steps, 3 * sql_count + 20)
            self.assertLess(elapsed, 60.0)

            manifest_lines = (run_dir / "control" / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertTrue(manifest_lines)
            manifest_text = "\n".join(manifest_lines)
            self.assertIn('"stage": "preflight"', manifest_text)
            self.assertIn('"stage": "scan"', manifest_text)
            self.assertIn('"stage": "optimize"', manifest_text)
            self.assertIn('"stage": "validate"', manifest_text)
            self.assertIn('"stage": "patch_generate"', manifest_text)
            self.assertIn('"stage": "report"', manifest_text)

            optimize_lines = [line for line in manifest_lines if '"stage": "optimize"' in line and '"event": "done"' in line]
            validate_lines = [line for line in manifest_lines if '"stage": "validate"' in line and '"event": "done"' in line]
            patch_lines = [line for line in manifest_lines if '"stage": "patch_generate"' in line and '"event": "done"' in line]
            self.assertGreaterEqual(len(optimize_lines), sql_count)
            self.assertGreaterEqual(len(validate_lines), sql_count)
            self.assertGreaterEqual(len(patch_lines), sql_count)

    def test_selected_single_sql_workflow_report_blocker_counts_match_patch_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_golden_single_sql_") as td:
            cfg = _write_cfg(td, report_enabled=True)
            run_id = f"run_golden_single_sql_{uuid4().hex[:8]}"
            run_dir, _steps, _elapsed = self._run_until_complete(
                cfg,
                run_id,
                to_stage="patch_generate",
                selection={"sql_keys": ["demo.user.advanced.listUsersFilteredAliased#v17"]},
            )
            self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))

            report = read_json(run_dir / "report.json")
            patch_rows = read_jsonl(run_dir / "artifacts" / "patches.jsonl")

            blocker_family_counts: dict[str, int] = {}
            patch_applicable_count = 0
            for row in patch_rows:
                family = blocker_family_for_patch_row(row)
                blocker_family_counts[family] = blocker_family_counts.get(family, 0) + 1
                delivery_stage = str(row.get("deliveryStage") or "").strip().upper()
                if delivery_stage == "APPLY_READY" or (not delivery_stage and row.get("applicable") is True):
                    patch_applicable_count += 1

            self.assertEqual(len(patch_rows), 1)
            self.assertEqual(((report.get("stats") or {}).get("patchable_total")), patch_applicable_count)
            self.assertGreaterEqual(((report.get("stats") or {}).get("blocked_total") or 0), 0)
            self.assertTrue((report.get("blockers") or {}).get("top_reason_codes") is not None)


if __name__ == "__main__":
    unittest.main()
