from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from sqlopt.llm.provider import _run_opencode


def _opencode_stdout() -> str:
    return (
        '{"type":"text","part":{"text":"{\\"candidates\\":[{\\"id\\":\\"c1\\",'
        '\\"rewrittenSql\\":\\"SELECT 1\\",\\"rewriteStrategy\\":\\"opencode_run\\"}]}"}}\n'
    )


class LlmOpencodeProviderTest(unittest.TestCase):
    def _prompt(self) -> dict:
        return {
            "sqlKey": "k1",
            "requiredContext": {"sql": "SELECT * FROM t"},
            "optionalContext": {},
        }

    def test_non_windows_keeps_dir_arg(self) -> None:
        cfg = {"opencode_workdir": "/tmp/work", "variant": "minimal"}
        fake = CompletedProcess(args=["opencode"], returncode=0, stdout=_opencode_stdout(), stderr="")
        with patch("sqlopt.llm.provider.shutil.which", return_value="/usr/bin/opencode"):
            with patch("sqlopt.llm.provider._is_windows", return_value=False):
                with patch("sqlopt.llm.provider.run_capture_text", return_value=fake) as run_mock:
                    _run_opencode("k1", self._prompt(), cfg)
        cmd = run_mock.call_args[0][0]
        self.assertIn("--dir", cmd)
        self.assertIn("/tmp/work", cmd)

    def test_windows_removes_dir_arg(self) -> None:
        cfg = {"opencode_workdir": "C:\\work\\repo", "variant": "minimal"}
        fake = CompletedProcess(args=["opencode"], returncode=0, stdout=_opencode_stdout(), stderr="")
        with patch("sqlopt.llm.provider.shutil.which", return_value="C:\\opencode.exe"):
            with patch("sqlopt.llm.provider._is_windows", return_value=True):
                with patch("sqlopt.llm.provider.run_capture_text", return_value=fake) as run_mock:
                    _run_opencode("k1", self._prompt(), cfg)
        cmd = run_mock.call_args[0][0]
        self.assertNotIn("--dir", cmd)


if __name__ == "__main__":
    unittest.main()
