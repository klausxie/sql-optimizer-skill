from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "ci" / "opencode_smoke_acceptance.py"
    spec = importlib.util.spec_from_file_location("opencode_smoke_acceptance", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OpencodeSmokeAcceptanceScriptTest(unittest.TestCase):
    def test_parse_last_dict_prefers_trailing_payload(self) -> None:
        module = _load_module()
        text = "\n".join(
            [
                "noise",
                "{'run_id': 'run_demo', 'complete': False}",
                '\x1b[0mwrapped {"run_id": "run_demo", "complete": true, "reason": "completed"} trailing',
            ]
        )
        payload = module._parse_last_dict(text)
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["reason"], "completed")

    def test_local_config_text_uses_offline_safe_defaults(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_smoke_cfg_") as td:
            repo_root = Path(td)
            jar_dir = repo_root / "java" / "scan-agent" / "target"
            jar_dir.mkdir(parents=True, exist_ok=True)
            jar_path = jar_dir / "scan-agent-1.0.0.jar"
            jar_path.write_text("stub", encoding="utf-8")

            text = module._local_config_text(repo_root)

        self.assertIn("provider: opencode_builtin", text)
        self.assertIn("mapper_globs:", text)
        self.assertIn("dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable", text)

    def test_latest_run_id_picks_most_recent_directory(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_smoke_runs_") as td:
            project_dir = Path(td)
            runs_dir = project_dir / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            older = runs_dir / "run_old"
            newer = runs_dir / "run_new"
            older.mkdir()
            time.sleep(0.01)
            newer.mkdir()

            run_id = module._latest_run_id(project_dir)

        self.assertEqual(run_id, "run_new")

    def test_main_uses_repo_cli_offline_smoke_path(self) -> None:
        module = _load_module()
        calls = []

        class _Proc:
            returncode = 0
            stdout = '{"run_id": "run_demo", "complete": true, "run_status": "COMPLETED"}'
            stderr = ""

        def fake_run(cmd, *, cwd=None):
            calls.append((cmd, cwd))
            return _Proc()

        with tempfile.TemporaryDirectory(prefix="sqlopt_smoke_acceptance_") as td:
            project_fixture = Path(td) / "fixture"
            project_fixture.mkdir(parents=True, exist_ok=True)
            (project_fixture / "runs").mkdir()
            local_repo = Path(td) / "repo"
            (local_repo / "tests" / "fixtures" / "projects").mkdir(parents=True, exist_ok=True)
            target_fixture = local_repo / "tests" / "fixtures" / "projects" / "sample_project"
            target_fixture.mkdir()
            (target_fixture / "runs").mkdir()
            (local_repo / "scripts").mkdir(parents=True, exist_ok=True)
            (local_repo / "scripts" / "sqlopt_cli.py").write_text("", encoding="utf-8")

            with patch.object(module, "_repo_root", return_value=local_repo):
                with patch.object(module, "_project_fixture", return_value=target_fixture):
                    with patch.object(module, "_run", side_effect=fake_run):
                        with patch.object(module, "_require_ok", return_value=None):
                            with patch.object(module, "_verify_outputs", return_value={"state_optimize": "DONE", "report_phase_status": "DONE", "proposals_present": True}):
                                with patch.object(module, "_latest_run_id", return_value="run_demo"):
                                    with patch.object(module, "_write_resolved_config", return_value=target_fixture / "config.resolved.json"):
                                        module.main()

        cli_calls = [cmd for cmd, _ in calls if cmd and "sqlopt_cli.py" in str(cmd[1] if len(cmd) > 1 else "")]
        self.assertGreaterEqual(len(cli_calls), 2, "expected repo sqlopt_cli run/status to be used")

    def test_write_resolved_config_forces_db_check_off(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_smoke_resolved_") as td:
            repo_root = Path(td)
            project_dir = repo_root / "project"
            project_dir.mkdir(parents=True, exist_ok=True)
            user_config_path = project_dir / "sqlopt.local.yml"
            user_config_path.write_text(module._local_config_text(repo_root), encoding="utf-8")

            resolved_path = module._write_resolved_config(repo_root, project_dir)
            payload = __import__("json").loads(resolved_path.read_text(encoding="utf-8"))

        self.assertEqual(resolved_path.name, "config.resolved.json")
        self.assertFalse(payload["validate"]["db_reachable"])


if __name__ == "__main__":
    unittest.main()
