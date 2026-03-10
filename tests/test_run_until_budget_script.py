from __future__ import annotations

import ast
import io
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


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
        payload = ast.literal_eval(proc.stdout.strip())
        self.assertFalse(payload["retryable"])

    def test_main_rebuilds_report_when_status_requests_it(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_until_budget_") as td:
            config_path = Path(td) / "sqlopt.yml"
            config_path.write_text("{}", encoding="utf-8")
            resolved_config = config_path.resolve()
            calls: list[tuple[str, ...]] = []
            responses = [
                mod.CliResult(0, {"run_id": "run_demo", "result": {"complete": False, "phase": "optimize"}}, "", ""),
                mod.CliResult(
                    0,
                    {
                        "run_id": "run_demo",
                        "complete": False,
                        "run_status": "COMPLETED",
                        "next_action": "report-rebuild",
                    },
                    "",
                    "",
                ),
                mod.CliResult(0, {"run_id": "run_demo", "result": {"complete": True, "phase": "report"}}, "", ""),
                mod.CliResult(
                    0,
                    {
                        "run_id": "run_demo",
                        "complete": True,
                        "current_phase": "report",
                        "remaining_statements": 0,
                    },
                    "",
                    "",
                ),
            ]

            def fake_run_cli(_repo_root: Path, *args: str):
                calls.append(tuple(args))
                return responses.pop(0)

            buf = io.StringIO()
            argv = [str(SCRIPT_PATH), "--config", str(config_path), "--max-steps", "4", "--max-seconds", "30"]
            with patch.object(mod, "_run_cli", side_effect=fake_run_cli):
                with patch.object(mod.time, "monotonic", return_value=0):
                    with patch.object(sys, "argv", argv):
                        with redirect_stdout(buf):
                            mod.main()

        self.assertEqual(calls[0], ("run", "--config", str(resolved_config), "--to-stage", "patch_generate", "--max-steps", "1"))
        self.assertEqual(calls[1], ("status", "--run-id", "run_demo"))
        self.assertEqual(
            calls[2],
            ("run", "--config", str(resolved_config), "--to-stage", "report", "--run-id", "run_demo", "--max-steps", "1"),
        )
        self.assertEqual(calls[3], ("status", "--run-id", "run_demo"))
        lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        payload = ast.literal_eval(lines[-1])
        self.assertEqual(payload["completion_mode"], "report-rebuild")

    def test_step_budget_uses_report_rebuild_continue_command(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_until_budget_") as td:
            config_path = Path(td) / "sqlopt.yml"
            config_path.write_text("{}", encoding="utf-8")
            responses = [
                mod.CliResult(0, {"run_id": "run_demo", "result": {"complete": False, "phase": "optimize"}}, "", ""),
                mod.CliResult(
                    0,
                    {
                        "run_id": "run_demo",
                        "complete": False,
                        "run_status": "COMPLETED",
                        "next_action": "report-rebuild",
                    },
                    "",
                    "",
                ),
            ]

            buf = io.StringIO()
            argv = [str(SCRIPT_PATH), "--config", str(config_path), "--max-steps", "1", "--max-seconds", "30"]
            with patch.object(mod, "_run_cli", side_effect=responses):
                with patch.object(mod.time, "monotonic", return_value=0):
                    with patch.object(sys, "argv", argv):
                        with redirect_stdout(buf):
                            mod.main()

        lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        payload = ast.literal_eval(lines[-1])
        self.assertEqual(payload["reason"], "step_budget_exhausted")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["next_mode"], "report-rebuild")
        self.assertIn("--to-stage report", payload["next_action"])
        self.assertIn("--run-id run_demo", payload["next_action"])
        self.assertIn("--max-steps 1", payload["next_action"])

    def test_main_reports_pipeline_completion_mode_by_default(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_until_budget_") as td:
            config_path = Path(td) / "sqlopt.yml"
            config_path.write_text("{}", encoding="utf-8")
            responses = [
                mod.CliResult(0, {"run_id": "run_demo", "result": {"complete": False, "phase": "optimize"}}, "", ""),
                mod.CliResult(
                    0,
                    {
                        "run_id": "run_demo",
                        "complete": True,
                        "current_phase": "patch_generate",
                        "remaining_statements": 0,
                    },
                    "",
                    "",
                ),
            ]

            buf = io.StringIO()
            argv = [str(SCRIPT_PATH), "--config", str(config_path), "--max-steps", "4", "--max-seconds", "30"]
            with patch.object(mod, "_run_cli", side_effect=responses):
                with patch.object(mod.time, "monotonic", return_value=0):
                    with patch.object(sys, "argv", argv):
                        with redirect_stdout(buf):
                            mod.main()

        lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        payload = ast.literal_eval(lines[-1])
        self.assertEqual(payload["completion_mode"], "pipeline")

    def test_next_invocation_uses_lifecycle_policy_for_report_rebuild(self) -> None:
        mod = _load_module()
        cfg = Path("/tmp/demo_sqlopt.yml")
        with patch.object(mod.lifecycle_policy, "status_requires_report_rebuild", return_value=True) as policy:
            invocation = mod._next_invocation(cfg, "run_demo", {"next_action": "resume"})
        self.assertEqual(invocation.mode, "report-rebuild")
        self.assertIn("--to-stage report", " ".join(invocation.cli_args))
        policy.assert_called_once_with({"next_action": "resume"})

    def test_follow_up_failure_reports_structured_next_mode(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_until_budget_") as td:
            config_path = Path(td) / "sqlopt.yml"
            config_path.write_text("{}", encoding="utf-8")
            responses = [
                mod.CliResult(0, {"run_id": "run_demo", "result": {"complete": False, "phase": "optimize"}}, "", ""),
                mod.CliResult(
                    0,
                    {
                        "run_id": "run_demo",
                        "complete": False,
                        "run_status": "COMPLETED",
                        "next_action": "report-rebuild",
                    },
                    "",
                    "",
                ),
                mod.CliResult(
                    2,
                    {"run_id": "run_demo", "error": {"reason_code": "REPORT_FAILED", "message": "report broke"}},
                    "",
                    "",
                ),
            ]

            buf = io.StringIO()
            argv = [str(SCRIPT_PATH), "--config", str(config_path), "--max-steps", "4", "--max-seconds", "30"]
            with patch.object(mod, "_run_cli", side_effect=responses):
                with patch.object(mod.time, "monotonic", return_value=0):
                    with patch.object(sys, "argv", argv):
                        with redirect_stdout(buf):
                            with self.assertRaises(SystemExit) as exc:
                                mod.main()

        self.assertEqual(exc.exception.code, 2)
        lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        payload = ast.literal_eval(lines[-1])
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["next_mode"], "report-rebuild")
        self.assertEqual(payload["error"]["reason_code"], "REPORT_FAILED")
        self.assertIn("--to-stage report", payload["details"]["next_recovery"])
        self.assertIn("--max-steps 1", payload["details"]["next_recovery"])


if __name__ == "__main__":
    unittest.main()
