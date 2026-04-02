from __future__ import annotations

import unittest

from sqlopt.platforms.mysql.compat import set_timeout_best_effort


class _DbError(Exception):
    def __init__(self, errno: int, message: str) -> None:
        super().__init__(message)
        self.errno = errno


class _Cursor:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.executed: list[str] = []

    def execute(self, sql: str) -> None:
        self.executed.append(sql)
        if self.exc is not None:
            raise self.exc


class MySqlCompatTest(unittest.TestCase):
    def test_set_timeout_best_effort_returns_true_when_supported(self) -> None:
        cursor = _Cursor()
        applied = set_timeout_best_effort(cursor, 3000)
        self.assertTrue(applied)
        self.assertEqual(len(cursor.executed), 1)

    def test_set_timeout_best_effort_returns_false_for_unsupported_timeout(self) -> None:
        cursor = _Cursor(_DbError(1193, "Unknown system variable 'MAX_EXECUTION_TIME'"))
        applied = set_timeout_best_effort(cursor, 3000)
        self.assertFalse(applied)

    def test_set_timeout_best_effort_raises_for_non_compatibility_error(self) -> None:
        cursor = _Cursor(_DbError(1227, "Access denied; you need (at least one of) the SUPER privilege(s)"))
        with self.assertRaises(_DbError):
            set_timeout_best_effort(cursor, 3000)


if __name__ == "__main__":
    unittest.main()
