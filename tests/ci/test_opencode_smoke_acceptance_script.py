from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path


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
        self.assertIn("dsn: postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable", text)

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


if __name__ == "__main__":
    unittest.main()
