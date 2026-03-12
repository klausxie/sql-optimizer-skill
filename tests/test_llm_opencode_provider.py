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

    def test_recovers_simple_cte_from_text_fallback(self) -> None:
        cfg = {"variant": "minimal"}
        text = (
            '{"type":"text","part":{"text":"The optimization candidates focus on:\\n'
            '1. **The CTE is redundant** - CTE adds overhead without benefit here\\n'
            '2. **Pushing ORDER BY into CTE**"}}\n'
        )
        fake = CompletedProcess(args=["opencode"], returncode=0, stdout=text, stderr="")
        prompt = {
            "sqlKey": "k1",
            "requiredContext": {
                "sql": "WITH recent_users AS (SELECT id, created_at FROM users) SELECT id, created_at FROM recent_users ORDER BY created_at DESC"
            },
            "optionalContext": {},
        }
        with patch("sqlopt.llm.provider.shutil.which", return_value="/usr/bin/opencode"):
            with patch("sqlopt.llm.provider._is_windows", return_value=False):
                with patch("sqlopt.llm.provider.run_capture_text", return_value=fake):
                    candidates, _ = _run_opencode("k1", prompt, cfg)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["rewriteStrategy"], "INLINE_SIMPLE_CTE_RECOVERED")
        self.assertEqual(
            candidates[0]["rewrittenSql"],
            "SELECT id, created_at FROM users ORDER BY created_at DESC",
        )

    def test_recovers_having_wrapper_from_text_fallback(self) -> None:
        cfg = {"variant": "minimal"}
        text = (
            '{"type":"text","part":{"text":"The first candidate removes the redundant subquery wrapper while preserving all original columns. '
            'Both maintain the exact GROUP BY and ORDER BY semantics."}}\n'
        )
        fake = CompletedProcess(args=["opencode"], returncode=0, stdout=text, stderr="")
        prompt = {
            "sqlKey": "k2",
            "requiredContext": {
                "sql": (
                    "SELECT user_id, COUNT(*) AS order_count FROM "
                    "(SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id HAVING COUNT(*) > 1) oc "
                    "ORDER BY user_id"
                )
            },
            "optionalContext": {},
        }
        with patch("sqlopt.llm.provider.shutil.which", return_value="/usr/bin/opencode"):
            with patch("sqlopt.llm.provider._is_windows", return_value=False):
                with patch("sqlopt.llm.provider.run_capture_text", return_value=fake):
                    candidates, _ = _run_opencode("k2", prompt, cfg)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["rewriteStrategy"], "REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED")
        self.assertEqual(
            candidates[0]["rewrittenSql"],
            "SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
        )


if __name__ == "__main__":
    unittest.main()
