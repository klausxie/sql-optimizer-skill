from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.devtools.harness.runtime import (
    HarnessHooks,
    load_run_artifacts,
    prepare_fixture_project,
    run_once,
    run_until_stage_complete,
    run_until_complete,
)


def _write_cfg(td: str, project_root: Path, *, report_enabled: bool = True) -> Path:
    cfg = Path(td) / "sqlopt.runtime.json"
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


class HarnessRuntimeTest(unittest.TestCase):
    def test_prepare_fixture_project_creates_mutable_git_initialized_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_harness_runtime_project_") as td:
            handle = prepare_fixture_project(Path(td), mutable=True, init_git=True)
            self.assertTrue(handle.root_path.exists())
            self.assertTrue((handle.root_path / ".git").exists())
            self.assertEqual(handle.name, "sample_project")
            self.assertNotEqual(handle.root_path.name, "projects")

    def test_run_until_complete_drives_workflow_with_preflight_hook(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_harness_runtime_run_") as td:
            handle = prepare_fixture_project(Path(td), mutable=True, init_git=True)
            cfg = _write_cfg(td, handle.root_path, report_enabled=True)
            run_id = f"run_runtime_{uuid4().hex[:8]}"

            result = run_until_complete(
                config_path=cfg,
                to_stage="patch_generate",
                run_id=run_id,
                repo_root=handle.root_path,
                hooks=HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True}),
            )
            self.assertTrue(result.status["complete"])
            self.assertGreaterEqual(result.steps, 1)
            self.assertEqual(result.run_id, run_id)
            self.assertEqual(result.run_dir, handle.root_path / "runs" / run_id)
            self.assertTrue((result.run_dir / "report.json").exists())

    def test_run_until_stage_complete_and_load_run_artifacts_return_core_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_harness_runtime_artifacts_") as td:
            handle = prepare_fixture_project(Path(td), mutable=True, init_git=True)
            cfg = _write_cfg(td, handle.root_path, report_enabled=True)
            run_id = f"run_runtime_artifacts_{uuid4().hex[:8]}"

            result = run_until_stage_complete(
                config_path=cfg,
                to_stage="scan",
                run_id=run_id,
                repo_root=handle.root_path,
                hooks=HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True}),
            )
            artifacts = load_run_artifacts(handle.root_path / "runs" / run_id)
            self.assertEqual(result.run_id, run_id)
            self.assertEqual(result.status["phase_status"]["scan"], "DONE")
            self.assertEqual(artifacts.state["run_id"], run_id)
            self.assertIn("phase_status", artifacts.state)
            self.assertTrue(artifacts.plan_path.exists())
            self.assertTrue(artifacts.manifest_path.exists())
            self.assertTrue(artifacts.scan_path.exists())


if __name__ == "__main__":
    unittest.main()
