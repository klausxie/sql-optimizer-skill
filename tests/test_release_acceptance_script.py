from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def _load_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "ci" / "release_acceptance.py"
    spec = importlib.util.spec_from_file_location("release_acceptance", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleaseAcceptanceScriptTest(unittest.TestCase):
    def test_parse_last_dict_prefers_trailing_payload(self) -> None:
        module = _load_module()
        text = "\n".join(
            [
                "noise",
                '{"ok": false}',
                "{'ok': True, 'step': 'done'}",
            ]
        )
        payload = module._parse_last_dict(text)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["step"], "done")

    def test_run_acceptance_step_requires_ok_payload(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_release_step_") as td:
            repo_root = Path(td)
            script_dir = repo_root / "scripts" / "ci"
            script_dir.mkdir(parents=True, exist_ok=True)
            (script_dir / "demo.py").write_text("", encoding="utf-8")

            class _Proc:
                returncode = 0
                stdout = '{"ok": true, "name": "demo"}'
                stderr = ""

            with patch.object(module.subprocess, "run", return_value=_Proc()):
                payload = module._run_acceptance_step(repo_root, "demo.py")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "demo")

    def test_main_runs_all_steps_and_prints_combined_payload(self) -> None:
        module = _load_module()
        calls: list[str] = []

        def fake_run(_repo_root, script_name):
            calls.append(script_name)
            return {"ok": True, "script": script_name}

        buf = io.StringIO()
        with patch.object(module, "_run_acceptance_step", side_effect=fake_run):
            with redirect_stdout(buf):
                module.main()

        self.assertEqual(
            calls,
            [
                "opencode_smoke_acceptance.py",
                "degraded_runtime_acceptance.py",
                "report_rebuild_acceptance.py",
                "verification_chain_acceptance.py",
            ],
        )
        payload = json.loads(buf.getvalue().strip())
        self.assertTrue(payload["ok"])
        self.assertIn("opencode_install_smoke", payload["steps"])
        self.assertIn("degraded_runtime", payload["steps"])
        self.assertIn("report_rebuild", payload["steps"])
        self.assertIn("verification_chain", payload["steps"])


if __name__ == "__main__":
    unittest.main()
