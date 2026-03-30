from __future__ import annotations

import ast
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlopt.cli import build_parser, cmd_apply, cmd_run, cmd_status
from sqlopt.errors import ConfigError


class CliRunDefaultsTest(unittest.TestCase):
    def _temp_config(self) -> tuple[str, tempfile.TemporaryDirectory[str]]:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cli_run_cfg_")
        cfg = Path(td.name) / "sqlopt.yml"
        cfg.write_text("{}", encoding="utf-8")
        return str(cfg), td

    def test_run_uses_default_config_when_omitted(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run"])
        self.assertEqual(args.cmd, "run")
        self.assertEqual(args.config, "sqlopt.yml")
        self.assertEqual(args.to_stage, "patch_generate")
        self.assertIsNone(args.run_id)
        self.assertEqual(args.max_steps, 0)
        self.assertEqual(args.max_seconds, 0)

    def test_cmd_run_reports_config_invalid_without_traceback(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id=None, max_steps=0, max_seconds=0)
        with td:
            with patch("sqlopt.cli.run_service.start_run", side_effect=ConfigError("bad config")):
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as ctx:
                        cmd_run(args)
        self.assertEqual(ctx.exception.code, 2)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertTrue(str(payload["run_id"]).startswith("run_"))
        self.assertEqual(payload["error"]["reason_code"], "CONFIG_INVALID")

    def test_cmd_run_loops_until_complete_by_default(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id=None, max_steps=0, max_seconds=0)
        with td:
            with patch("sqlopt.cli.run_service.start_run", return_value=("run_demo", {"complete": False, "phase": "scan"})):
                with patch(
                    "sqlopt.cli.run_service.resume_run",
                    side_effect=[{"complete": False, "phase": "optimize"}, {"complete": True, "phase": "report"}],
                ) as mock_resume:
                    with redirect_stdout(buf):
                        cmd_run(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["steps_executed"], 3)
        self.assertEqual(payload["result"]["phase"], "report")
        self.assertEqual(mock_resume.call_count, 2)

    def test_cmd_run_reports_run_id_at_start(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id="run_demo", max_steps=1, max_seconds=0)
        with td:
            with patch("sqlopt.cli.get_progress_reporter") as mock_reporter:
                mock_reporter.return_value.report_info.return_value = None
                with patch("sqlopt.cli.run_service.start_run", return_value=("run_demo", {"complete": False, "phase": "scan"})):
                    with patch("sqlopt.cli.run_service.resume_run"):
                        with redirect_stdout(buf):
                            cmd_run(args)
        mock_reporter.return_value.report_info.assert_called_once_with("run_id=run_demo")

    def test_cmd_resume_loops_until_complete_by_default(self) -> None:
        from sqlopt.cli import cmd_resume

        buf = io.StringIO()
        args = SimpleNamespace(run_id="run_demo", max_steps=0, max_seconds=0)
        with patch(
            "sqlopt.cli.run_service.resume_run",
            side_effect=[{"complete": False, "phase": "validate"}, {"complete": True, "phase": "report"}],
        ) as mock_resume:
            with redirect_stdout(buf):
                cmd_resume(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["steps_executed"], 2)
        self.assertEqual(payload["result"]["phase"], "report")
        self.assertEqual(mock_resume.call_count, 2)

    def test_cmd_resume_reports_run_id_at_start(self) -> None:
        from sqlopt.cli import cmd_resume

        buf = io.StringIO()
        args = SimpleNamespace(run_id="run_demo", project=".", max_steps=1, max_seconds=0)
        with patch("sqlopt.cli.get_progress_reporter") as mock_reporter:
            mock_reporter.return_value.report_info.return_value = None
            with patch("sqlopt.cli.run_service.resume_run", return_value={"complete": False, "phase": "optimize"}):
                with redirect_stdout(buf):
                    cmd_resume(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["reason"], "step_budget_exhausted")
        mock_reporter.return_value.report_info.assert_called_once_with("run_id=run_demo")

    def test_status_resume_apply_accept_optional_run_id_with_project_default(self) -> None:
        parser = build_parser()

        status_args = parser.parse_args(["status"])
        self.assertEqual(status_args.run_id, None)
        self.assertEqual(status_args.project, ".")

        resume_args = parser.parse_args(["resume"])
        self.assertEqual(resume_args.run_id, None)
        self.assertEqual(resume_args.project, ".")
        self.assertEqual(resume_args.max_steps, 0)
        self.assertEqual(resume_args.max_seconds, 0)

        apply_args = parser.parse_args(["apply"])
        self.assertEqual(apply_args.run_id, None)
        self.assertEqual(apply_args.project, ".")

    def test_cmd_status_resolves_latest_when_run_id_omitted(self) -> None:
        buf = io.StringIO()
        args = SimpleNamespace(run_id=None, project=".")
        with patch("sqlopt.cli.resolve_run_id", return_value=("run_latest", Path("/tmp/run_latest"))):
            with patch("sqlopt.cli.run_service.get_status", return_value={"run_id": "run_latest", "complete": False}) as mock_status:
                with redirect_stdout(buf):
                    cmd_status(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_latest")
        self.assertFalse(payload["complete"])
        mock_status.assert_called_once_with("run_latest", repo_root=Path.cwd().resolve())

    def test_cmd_apply_resolves_latest_when_run_id_omitted(self) -> None:
        buf = io.StringIO()
        args = SimpleNamespace(run_id=None, project=".")
        with patch("sqlopt.cli.resolve_run_id", return_value=("run_latest", Path("/tmp/run_latest"))):
            with patch("sqlopt.cli.run_service.apply_run", return_value={"run_id": "run_latest", "apply": {"applied": False}}) as mock_apply:
                with redirect_stdout(buf):
                    cmd_apply(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_latest")
        self.assertEqual(payload["apply"]["applied"], False)
        mock_apply.assert_called_once_with("run_latest", repo_root=Path.cwd().resolve())

    def test_cmd_resume_resolves_latest_when_run_id_omitted(self) -> None:
        from sqlopt.cli import cmd_resume

        buf = io.StringIO()
        args = SimpleNamespace(run_id=None, project=".", max_steps=0, max_seconds=0)
        with patch("sqlopt.cli.resolve_run_id", return_value=("run_latest", Path("/tmp/run_latest"))):
            with patch("sqlopt.cli.run_service.resume_run", side_effect=[{"complete": False}, {"complete": True, "phase": "report"}]) as mock_resume:
                with redirect_stdout(buf):
                    cmd_resume(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_latest")
        self.assertTrue(payload["complete"])
        self.assertEqual(mock_resume.call_count, 2)

    def test_status_resume_apply_report_run_not_found_for_missing_latest(self) -> None:
        from sqlopt.cli import cmd_resume

        missing_args = SimpleNamespace(run_id=None, project=".", max_steps=0, max_seconds=0)

        with patch("sqlopt.cli.resolve_run_id", side_effect=FileNotFoundError("latest")):
            for fn in (cmd_status, cmd_apply, cmd_resume):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as ctx:
                        fn(missing_args)
                self.assertEqual(ctx.exception.code, 2)
                payload = ast.literal_eval(buf.getvalue().strip())
                self.assertEqual(payload["run_id"], "latest")
                self.assertEqual(payload["error"]["reason_code"], "RUN_NOT_FOUND")

    def test_cmd_run_respects_step_budget(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id=None, max_steps=1, max_seconds=0)
        with td:
            with patch("sqlopt.cli.run_service.start_run", return_value=("run_demo", {"complete": False, "phase": "scan"})):
                with patch("sqlopt.cli.run_service.resume_run") as mock_resume:
                    with redirect_stdout(buf):
                        cmd_run(args)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["reason"], "step_budget_exhausted")
        self.assertEqual(payload["steps_executed"], 1)
        self.assertEqual(mock_resume.call_count, 0)

    def test_cmd_run_reports_run_not_found_during_auto_resume(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id=None, max_steps=0, max_seconds=0)
        with td:
            with patch("sqlopt.cli.run_service.start_run", return_value=("run_demo", {"complete": False, "phase": "scan"})):
                with patch("sqlopt.cli.run_service.resume_run", side_effect=FileNotFoundError("run_demo")):
                    with redirect_stdout(buf):
                        with self.assertRaises(SystemExit) as ctx:
                            cmd_run(args)
        self.assertEqual(ctx.exception.code, 2)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertEqual(payload["error"]["reason_code"], "RUN_NOT_FOUND")

    def test_cmd_run_interrupt_outputs_compact_payload(self) -> None:
        buf = io.StringIO()
        cfg, td = self._temp_config()
        args = SimpleNamespace(config=cfg, to_stage="patch_generate", run_id=None, max_steps=0, max_seconds=0)
        with td:
            with patch("sqlopt.cli.run_service.start_run", return_value=("run_demo", {"complete": False, "phase": "scan"})):
                with patch("sqlopt.cli.run_service.resume_run", side_effect=KeyboardInterrupt()):
                    with redirect_stdout(buf):
                        with self.assertRaises(SystemExit) as ctx:
                            cmd_run(args)
        self.assertEqual(ctx.exception.code, 130)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["interrupted"])
        self.assertTrue(payload["retryable"])
        self.assertIn("sqlopt-cli resume --run-id run_demo", payload.get("next_action", ""))

    def test_cmd_resume_interrupt_outputs_compact_payload(self) -> None:
        from sqlopt.cli import cmd_resume

        buf = io.StringIO()
        args = SimpleNamespace(run_id="run_demo", project=".", max_steps=0, max_seconds=0)
        with patch("sqlopt.cli.run_service.resume_run", side_effect=KeyboardInterrupt()):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    cmd_resume(args)
        self.assertEqual(ctx.exception.code, 130)
        payload = ast.literal_eval(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "run_demo")
        self.assertTrue(payload["interrupted"])
        self.assertTrue(payload["retryable"])
        self.assertIn("sqlopt-cli resume --run-id run_demo", payload.get("next_action", ""))


if __name__ == "__main__":
    unittest.main()
