from __future__ import annotations

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
from sqlopt.devtools.harness.runtime import HarnessHooks, load_run_artifacts, prepare_fixture_project, run_once, run_until_complete


class WorkflowSupervisorTest(unittest.TestCase):
    HOOKS = HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True})

    def _write_cfg(self, td: str, project_root: Path, *, report_enabled: bool = True, mapper_glob: str | None = None) -> Path:
        cfg = Path(td) / "sqlopt.yml"
        mapper = mapper_glob or "src/main/resources/com/example/mapper/user/user_mapper.xml"
        report_flag = "true" if report_enabled else "false"
        cfg.write_text(
            "\n".join(
                [
                    "project:",
                    f"  root_path: {str(project_root.resolve())}",
                    "scan:",
                    "  mapper_globs:",
                    f"    - {mapper}",
                    "db:",
                    "  platform: postgresql",
                    "  dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
                    "report:",
                    f"  enabled: {report_flag}",
                    "llm:",
                    "  enabled: false",
                    "  provider: heuristic",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return cfg

    def test_patch_generate_auto_finalizes_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = self._write_cfg(td, project_root)
            run_id = f"run_supervisor_auto_report_{uuid4().hex[:8]}"
            run_until_complete(
                config_path=cfg,
                to_stage="patch_generate",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )

            run_dir = project_root / "runs" / run_id
            artifacts = load_run_artifacts(run_dir)
            assert_report_generated(artifacts)
            assert_phase_status(artifacts, "report", "DONE")
            assert_run_completed(artifacts)
            assert_manifest_contains_stages(
                artifacts,
                ["preflight", "scan", "optimize", "validate", "patch_generate", "report"],
            )

    def test_optimize_stage_still_generates_report_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = self._write_cfg(td, project_root)
            run_id = f"run_supervisor_optimize_report_{uuid4().hex[:8]}"
            run_until_complete(
                config_path=cfg,
                to_stage="optimize",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )

            run_dir = project_root / "runs" / run_id
            artifacts = load_run_artifacts(run_dir)
            assert_report_generated(artifacts)
            assert_phase_status(artifacts, "optimize", "DONE")
            assert_phase_status(artifacts, "validate", "SKIPPED")
            assert_phase_status(artifacts, "patch_generate", "SKIPPED")
            assert_phase_status(artifacts, "report", "DONE")

    def test_optimize_stage_skips_report_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = self._write_cfg(td, project_root, report_enabled=False)
            run_id = f"run_supervisor_optimize_no_report_{uuid4().hex[:8]}"
            run_until_complete(
                config_path=cfg,
                to_stage="optimize",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )

            run_dir = project_root / "runs" / run_id
            artifacts = load_run_artifacts(run_dir)
            self.assertFalse((run_dir / "report.json").exists())
            assert_phase_status(artifacts, "report", "SKIPPED")
            assert_run_completed(artifacts)

    def test_explicit_report_rebuild_does_not_append_duplicate_done_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
            cfg = self._write_cfg(td, project_root)
            run_id = f"run_supervisor_report_rebuild_{uuid4().hex[:8]}"
            run_until_complete(
                config_path=cfg,
                to_stage="patch_generate",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )

            run_dir = project_root / "runs" / run_id
            manifest_path = run_dir / "control" / "manifest.jsonl"
            before_lines = [
                line
                for line in manifest_path.read_text(encoding="utf-8").strip().splitlines()
                if '"stage": "report"' in line and '"event": "done"' in line
            ]

            run_once(
                config_path=cfg,
                to_stage="report",
                run_id=run_id,
                repo_root=project_root,
                hooks=self.HOOKS,
            )

            after_lines = [
                line
                for line in manifest_path.read_text(encoding="utf-8").strip().splitlines()
                if '"stage": "report"' in line and '"event": "done"' in line
            ]
            artifacts = load_run_artifacts(run_dir)
            self.assertEqual(len(before_lines), 1)
            self.assertEqual(len(after_lines), 1)
            assert_report_rebuild_cleared(artifacts)


if __name__ == "__main__":
    unittest.main()
