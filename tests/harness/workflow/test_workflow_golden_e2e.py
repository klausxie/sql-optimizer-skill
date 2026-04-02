from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.devtools.harness.assertions import (
    assert_manifest_contains_stages,
    assert_phase_status,
    assert_report_generated,
    assert_report_rebuild_cleared,
    assert_run_completed,
)
from sqlopt.devtools.harness.runtime import (
    FIXTURE_PROJECT_ROOT,
    HarnessHooks,
    apply_once,
    load_run_artifacts,
    prepare_fixture_project,
    run_once,
    run_until_complete,
    status_once,
)
from sqlopt.io_utils import read_json, read_jsonl, write_json
from sqlopt.stages.report_stats import blocker_family_for_patch_row


def _write_cfg(td: str, project_root: Path, *, report_enabled: bool = True) -> Path:
    cfg = Path(td) / "sqlopt.json"
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

class WorkflowGoldenE2ETest(unittest.TestCase):
    HOOKS = HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True})

    def _run_until_complete(
        self,
        config: Path,
        run_id: str,
        *,
        project_root: Path,
        to_stage: str,
        selection: dict[str, object] | None = None,
    ) -> tuple[Path, int, float]:
        result = run_until_complete(
            config_path=config,
            to_stage=to_stage,
            run_id=run_id,
            repo_root=project_root,
            selection=selection,
            hooks=self.HOOKS,
        )
        return result.run_dir, result.steps, result.elapsed_seconds

    def test_run_resume_status_report_rebuild_apply_golden(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_golden_e2e_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = _write_cfg(td, project_root, report_enabled=True)
            run_id = f"run_golden_e2e_{uuid4().hex[:8]}"
            run_dir, _steps, _elapsed = self._run_until_complete(
                cfg,
                run_id,
                project_root=project_root,
                to_stage="patch_generate",
            )
            self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))
            self.assertNotIn(FIXTURE_PROJECT_ROOT, run_dir.parents)
            self.assertIn(project_root, run_dir.parents)
            artifacts = load_run_artifacts(run_dir)

            status = status_once(run_id=run_id, repo_root=project_root)
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

            state = artifacts.state
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
            assert_run_completed(artifacts)
            assert_report_rebuild_cleared(artifacts)

            report = artifacts.report
            assert_report_generated(artifacts)
            self.assertEqual(report["target_stage"], "report")
            assert_phase_status(artifacts, "report", "DONE")
            self.assertIn(report["next_action"], {"apply", "inspect", "resume"})
            self.assertGreaterEqual(int((report.get("stats") or {}).get("sql_total") or 0), 1)
            self.assertIn("top_reason_codes", report.get("blockers") or {})

            apply_result = apply_once(run_id=run_id, repo_root=project_root)
            self.assertEqual(apply_result["run_id"], run_id)
            self.assertEqual((apply_result.get("apply") or {}).get("mode"), "PATCH_ONLY")
            self.assertTrue((run_dir / "apply" / "state.json").exists())

            # Simulate a completed run requiring report rebuild and verify next_action.
            state["report_rebuild_required"] = True
            write_json(run_dir / "control" / "state.json", state)
            rebuild_status = status_once(run_id=run_id, repo_root=project_root)
            self.assertEqual(rebuild_status["next_action"], "report-rebuild")

            # Rebuild report on the same run_id; ensure rebuild flag is cleared.
            run_once(
                config_path=cfg,
                to_stage="report",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )
            post_rebuild_status = status_once(run_id=run_id, repo_root=project_root)
            self.assertTrue(post_rebuild_status["complete"])
            self.assertEqual(post_rebuild_status["next_action"], "none")
            post_artifacts = load_run_artifacts(run_dir)
            assert_report_rebuild_cleared(post_artifacts)

    def test_runtime_step_count_stays_within_baseline_envelope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_perf_baseline_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = _write_cfg(td, project_root, report_enabled=True)
            run_id = f"run_perf_baseline_{uuid4().hex[:8]}"
            run_dir, steps, elapsed = self._run_until_complete(
                cfg,
                run_id,
                project_root=project_root,
                to_stage="patch_generate",
            )
            self.addCleanup(lambda: shutil.rmtree(run_dir, ignore_errors=True))

            plan = read_json(run_dir / "control" / "plan.json")
            sql_count = len(list(plan.get("sql_keys") or []))
            # Envelope: 3 statement phases per SQL + phase transitions/finalization buffer.
            self.assertLessEqual(steps, 3 * sql_count + 20)
            self.assertLess(elapsed, 60.0)

            artifacts = load_run_artifacts(run_dir)
            manifest_lines = (run_dir / "control" / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertTrue(manifest_lines)
            assert_manifest_contains_stages(
                artifacts,
                ["preflight", "scan", "optimize", "validate", "patch_generate", "report"],
            )

            optimize_lines = [line for line in manifest_lines if '"stage": "optimize"' in line and '"event": "done"' in line]
            validate_lines = [line for line in manifest_lines if '"stage": "validate"' in line and '"event": "done"' in line]
            patch_lines = [line for line in manifest_lines if '"stage": "patch_generate"' in line and '"event": "done"' in line]
            self.assertGreaterEqual(len(optimize_lines), sql_count)
            self.assertGreaterEqual(len(validate_lines), sql_count)
            self.assertGreaterEqual(len(patch_lines), sql_count)

    def test_selected_single_sql_workflow_report_blocker_counts_match_patch_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_golden_single_sql_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = _write_cfg(td, project_root, report_enabled=True)
            run_id = f"run_golden_single_sql_{uuid4().hex[:8]}"
            run_dir, _steps, _elapsed = self._run_until_complete(
                cfg,
                run_id,
                project_root=project_root,
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
