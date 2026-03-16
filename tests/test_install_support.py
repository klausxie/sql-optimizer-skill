from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt import install_support


class InstallSupportTest(unittest.TestCase):
    def test_write_cli_wrapper_windows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_inst_") as td:
            root = Path(td)
            with patch(
                "sqlopt.install_support.platform.system", return_value="Windows"
            ):
                wrapper = install_support.write_cli_wrapper(root)
            self.assertEqual(wrapper.name, "sqlopt-cli.cmd")
            text = wrapper.read_text(encoding="utf-8")
            self.assertIn(r".venv\Scripts\python.exe", text)
            self.assertIn(r"%ROOT_DIR%\scripts\sqlopt_cli.py", text)

    def test_write_cli_wrapper_unix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_inst_") as td:
            root = Path(td)
            with patch("sqlopt.install_support.platform.system", return_value="Linux"):
                wrapper = install_support.write_cli_wrapper(root)
            self.assertEqual(wrapper.name, "sqlopt-cli")
            text = wrapper.read_text(encoding="utf-8")
            self.assertIn('exec "$ROOT_DIR/.venv/bin/python"', text)
            self.assertIn('"$ROOT_DIR/scripts/sqlopt_cli.py"', text)

    def test_cli_run_command_windows(self) -> None:
        wrapper = Path(r"C:\Users\a\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd")
        with patch("sqlopt.install_support.platform.system", return_value="Windows"):
            cmd = install_support.cli_run_command(wrapper, "status", "--run-id", "r1")
        self.assertEqual(cmd[:2], ["cmd", "/c"])
        self.assertEqual(cmd[2], str(wrapper))

    def test_cli_run_command_windows_with_spaces(self) -> None:
        wrapper = Path(
            r"C:\Users\a user\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd"
        )
        with patch("sqlopt.install_support.platform.system", return_value="Windows"):
            cmd = install_support.cli_run_command(wrapper, "status", "--run-id", "r1")
        self.assertEqual(cmd[2], str(wrapper))
        self.assertEqual(cmd[3:], ["status", "--run-id", "r1"])


if __name__ == "__main__":
    unittest.main()
