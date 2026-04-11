from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "ci" / "degraded_runtime_acceptance.py"
    spec = importlib.util.spec_from_file_location("degraded_runtime_acceptance", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DegradedRuntimeAcceptanceScriptTest(unittest.TestCase):
    def test_parse_last_dict_prefers_trailing_payload(self) -> None:
        module = _load_module()
        text = "\n".join(
            [
                "noise",
                '{"run_id": "run_demo", "complete": false}',
                "{'run_id': 'run_demo', 'complete': True, 'reason': 'completed'}",
            ]
        )
        payload = module._parse_last_dict(text)
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["reason"], "completed")

    def test_config_text_uses_degraded_defaults(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_degraded_cfg_") as td:
            repo_root = Path(td)
            jar_dir = repo_root / "java" / "scan-agent" / "target"
            jar_dir.mkdir(parents=True, exist_ok=True)
            jar_path = jar_dir / "scan-agent-1.0.0.jar"
            jar_path.write_text("stub", encoding="utf-8")

            text = module._config_text(repo_root)

        self.assertIn("dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable", text)
        self.assertIn("provider: opencode_builtin", text)

    def test_write_resolved_config_forces_db_check_off(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_degraded_resolved_") as td:
            repo_root = Path(td)
            project_dir = repo_root / "project"
            project_dir.mkdir(parents=True, exist_ok=True)
            user_config_path = project_dir / "sqlopt.local.yml"
            user_config_path.write_text(module._config_text(repo_root), encoding="utf-8")

            resolved_path = module._write_resolved_config(project_dir)
            payload = __import__("json").loads(resolved_path.read_text(encoding="utf-8"))

        self.assertEqual(resolved_path.name, "config.resolved.json")
        self.assertFalse(payload["validate"]["db_reachable"])


if __name__ == "__main__":
    unittest.main()
