from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_until_budget.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_until_budget_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class RunUntilBudgetScriptTest(unittest.TestCase):
    def test_parse_payload_supports_python_repr(self) -> None:
        mod = _load_module()
        payload = mod._parse_payload("{'run_id': 'r1', 'complete': False}\n")
        self.assertEqual(payload, {"run_id": "r1", "complete": False})

    def test_missing_config_returns_nonzero(self) -> None:
        proc = subprocess.run(
            ["python3", str(SCRIPT_PATH), "--config", "/tmp/definitely_missing_sqlopt.yml"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("CONFIG_NOT_FOUND", proc.stdout)


if __name__ == "__main__":
    unittest.main()
