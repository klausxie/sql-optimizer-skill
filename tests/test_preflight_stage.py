from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.errors import StageError
from sqlopt.io_utils import read_json
from sqlopt.stages import preflight


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class PreflightStageTest(unittest.TestCase):
    class _Resp:
        def __init__(self, body: str):
            self._body = body

        def read(self) -> bytes:
            return self._body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def test_preflight_pass_when_checks_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_ok"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "llm": {"enabled": False},
                "scan": {},
            }
            result = preflight.execute(config, run_dir)
            self.assertTrue(result.get("ok"))
            saved = read_json(run_dir / "pipeline" / "ops" / "preflight.json")
            self.assertTrue(saved.get("ok"))

    def test_preflight_fail_when_opencode_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_fail"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "scan": {},
                "llm": {"enabled": True, "provider": "opencode_run", "timeout_ms": 1000},
            }
            with patch("sqlopt.stages.preflight.shutil.which", return_value="/usr/bin/opencode"):
                with patch("sqlopt.stages.preflight.run_capture_text", return_value=_Proc(1, "", "network down")):
                    with self.assertRaises(StageError) as cm:
                        preflight.execute(config, run_dir)
            self.assertEqual(cm.exception.reason_code, "PREFLIGHT_LLM_UNREACHABLE")
            saved = read_json(run_dir / "pipeline" / "ops" / "preflight.json")
            self.assertFalse(saved.get("ok"))

    def test_preflight_skips_db_check_when_platform_capability_disables_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_db_capability"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "db": {"platform": "postgresql"},
                "validate": {"db_reachable": True},
                "llm": {"enabled": False},
                "scan": {},
            }
            with patch("sqlopt.stages.preflight_strategy.get_platform_capabilities") as caps:
                caps.return_value.supports_connectivity_check = False
                result = preflight.execute(config, run_dir)

            self.assertTrue(result.get("ok"))
            db_check = next(row for row in result["checks"] if row.get("name") == "db")
            self.assertEqual(db_check.get("reason"), "platform capability disables connectivity check")

    def test_preflight_skips_external_llm_checks_for_builtin_provider(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_llm_skip"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "scan": {},
                "llm": {"enabled": True, "provider": "opencode_builtin"},
            }
            with patch("sqlopt.stages.preflight._check_opencode") as opencode_mock:
                with patch("sqlopt.stages.preflight._check_direct_openai") as direct_mock:
                    result = preflight.execute(config, run_dir)

            opencode_mock.assert_not_called()
            direct_mock.assert_not_called()
            llm_check = next(row for row in result["checks"] if row.get("name") == "llm")
            self.assertEqual(llm_check.get("reason"), "provider=opencode_builtin")

    def test_preflight_scanner_check_stays_skipped_even_with_legacy_java_scanner_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_scanner_legacy"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "scan": {"java_scanner": {"jar_path": str(Path(td) / "missing.jar")}},
                "llm": {"enabled": False},
            }
            result = preflight.execute(config, run_dir)
            scanner_check = next(row for row in result["checks"] if row.get("name") == "scanner")
            self.assertTrue(scanner_check.get("ok"))
            self.assertFalse(scanner_check.get("enabled"))

    def test_preflight_direct_openai_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_direct_ok"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "scan": {},
                "llm": {
                    "enabled": True,
                    "provider": "direct_openai_compatible",
                    "api_base": "https://example.com/v1",
                    "api_key": "k",
                    "api_model": "m",
                    "timeout_ms": 1000,
                },
            }
            with patch("sqlopt.stages.preflight.urllib.request.urlopen", return_value=self._Resp('{"choices":[{"message":{"content":"ok"}}]}')):
                result = preflight.execute(config, run_dir)
            self.assertTrue(result.get("ok"))

    def test_preflight_direct_openai_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_preflight_") as td:
            run_dir = Path(td) / "runs" / "run_pf_direct_fail"
            (run_dir / "pipeline" / "ops").mkdir(parents=True, exist_ok=True)
            config = {
                "project": {"root_path": str(Path(td).resolve())},
                "validate": {"db_reachable": False},
                "scan": {},
                "llm": {
                    "enabled": True,
                    "provider": "direct_openai_compatible",
                    "api_base": "https://example.com/v1",
                    "api_key": "k",
                    "api_model": "m",
                    "timeout_ms": 1000,
                },
            }
            with patch("sqlopt.stages.preflight.urllib.request.urlopen", side_effect=RuntimeError("network down")):
                with self.assertRaises(StageError) as cm:
                    preflight.execute(config, run_dir)
            self.assertEqual(cm.exception.reason_code, "PREFLIGHT_LLM_UNREACHABLE")


if __name__ == "__main__":
    unittest.main()
