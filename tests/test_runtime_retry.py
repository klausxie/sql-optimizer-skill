from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from sqlopt.errors import StageError
from sqlopt import runtime as runtime_mod
from sqlopt.runtime import execute_with_retry


class RuntimeRetryTest(unittest.TestCase):
    def test_timeout_raises_stage_timeout(self) -> None:
        def slow() -> None:
            time.sleep(0.05)

        if runtime_mod.HAS_POSIX_ALARM:
            with self.assertRaises(StageError) as cm:
                execute_with_retry("optimize", slow, timeout_ms=1, retry_max=0, retry_backoff_ms=1)
            self.assertEqual(cm.exception.reason_code, "RUNTIME_STAGE_TIMEOUT")
            return
        result, attempts = execute_with_retry("optimize", slow, timeout_ms=1, retry_max=0, retry_backoff_ms=1)
        self.assertIsNone(result)
        self.assertEqual(attempts, 1)

    def test_exception_raises_retry_exhausted(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        with self.assertRaises(StageError) as cm:
            execute_with_retry("validate", boom, timeout_ms=1000, retry_max=0, retry_backoff_ms=1)
        self.assertEqual(cm.exception.reason_code, "RUNTIME_RETRY_EXHAUSTED")

    def test_windows_soft_timeout_branch_no_sigalrm_dependency(self) -> None:
        with patch("sqlopt.runtime.HAS_POSIX_ALARM", False):
            result, attempts = execute_with_retry("scan", lambda: "ok", timeout_ms=1, retry_max=0, retry_backoff_ms=1)
        self.assertEqual(result, "ok")
        self.assertEqual(attempts, 1)


if __name__ == "__main__":
    unittest.main()
