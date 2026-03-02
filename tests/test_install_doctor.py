from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_doctor_module():
    path = ROOT / "install" / "doctor.py"
    spec = importlib.util.spec_from_file_location("install_doctor_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallDoctorTest(unittest.TestCase):
    def test_run_check_handles_missing_command(self) -> None:
        module = _load_doctor_module()
        out = io.StringIO()
        with patch.object(module, "run_capture_text", side_effect=FileNotFoundError("opencode not found")):
            with contextlib.redirect_stdout(out):
                ok = module._run_check("opencode available", ["opencode", "--version"])
        self.assertFalse(ok)
        text = out.getvalue()
        self.assertIn("[FAIL] opencode available", text)
        self.assertIn("opencode not found", text)

    def test_make_run_id_is_unique(self) -> None:
        module = _load_doctor_module()
        a = module._make_run_id()
        b = module._make_run_id()
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("run_doctor_"))
        self.assertTrue(b.startswith("run_doctor_"))


if __name__ == "__main__":
    unittest.main()
