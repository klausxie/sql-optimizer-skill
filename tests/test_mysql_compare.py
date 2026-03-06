from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.platforms.mysql import compare


class _Cursor:
    def __init__(self, script: list[object], execute_errors: list[Exception] | None = None) -> None:
        self._script = list(script)
        self._execute_errors = list(execute_errors or [])

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: object | None = None) -> None:
        if self._execute_errors:
            raise self._execute_errors.pop(0)
        return None

    def fetchone(self):
        if not self._script:
            return None
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Conn:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Conn":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _Cursor:
        return self._cursor


class MySqlCompareTest(unittest.TestCase):
    def test_compare_plan_respects_config_and_driver_guards(self) -> None:
        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {"plan_compare_enabled": False}}
        self.assertEqual(compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path("."))["reasonCategory"], "PLAN_COMPARE_DISABLED")

        cfg = {"db": {"platform": "mysql"}, "validate": {}}
        self.assertEqual(compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path("."))["reasonCategory"], "NO_DSN")

        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {}}
        with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(None, None)):
            self.assertEqual(compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path("."))["reasonCategory"], "DRIVER_NOT_INSTALLED")

    def test_compare_plan_reports_prepare_failure(self) -> None:
        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {}}
        with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(_Cursor([])), "pymysql")):
            result = compare.compare_plan(cfg, "SELECT 1", "<if test='x'></if>", Path("."))
        self.assertEqual(result["reasonCategory"], "SQL_PREPARE_FAILED")

    def test_compare_plan_extracts_cost_and_marks_improvement(self) -> None:
        cfg = {
            "db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"},
            "validate": {},
            "policy": {"cost_threshold_pct": 0},
        }
        cursor = _Cursor(
            [
                ('{"query_block":{"cost_info":{"query_cost":"15.0"}}}',),
                ('{"query_block":{"cost_info":{"query_cost":"7.5"}}}',),
            ]
        )
        with tempfile.TemporaryDirectory(prefix="sqlopt_mysql_compare_") as td:
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
                result = compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path(td))
        self.assertTrue(result["checked"])
        self.assertTrue(result["improved"])
        self.assertEqual(result["reasonCodes"], ["TOTAL_COST_REDUCED"])
        self.assertEqual(result["beforeSummary"]["totalCost"], 15.0)
        self.assertEqual(result["afterSummary"]["totalCost"], 7.5)

    def test_compare_plan_tolerates_unsupported_timeout_setting(self) -> None:
        cfg = {
            "db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"},
            "validate": {},
            "policy": {"cost_threshold_pct": 0},
        }
        cursor = _Cursor(
            [
                ('{"query_block":{"cost_info":{"query_cost":"15.0"}}}',),
                ('{"query_block":{"cost_info":{"query_cost":"7.5"}}}',),
            ],
            execute_errors=[RuntimeError("Unknown system variable 'MAX_EXECUTION_TIME'")],
        )
        with tempfile.TemporaryDirectory(prefix="sqlopt_mysql_compare_") as td:
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
                result = compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path(td))

        self.assertTrue(result["checked"])
        self.assertTrue(result["improved"])

    def test_compare_plan_supports_db_unreachable_fallback(self) -> None:
        cfg = {
            "db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"},
            "validate": {"allow_db_unreachable_fallback": True},
        }
        with patch(
            "sqlopt.platforms.mysql.compare._get_sql_connect",
            return_value=(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("can't connect to mysql server")), "pymysql"),
        ):
            result = compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path("."))
        self.assertEqual(result["reasonCategory"], "DB_UNREACHABLE")

    def test_compare_plan_extracts_estimated_total_cost_from_new_json_schema(self) -> None:
        cfg = {
            "db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"},
            "validate": {},
            "policy": {"cost_threshold_pct": 0},
        }
        cursor = _Cursor(
            [
                ('{"query_plan":{"estimated_total_cost":8.0}}',),
                ('{"query_plan":{"estimated_total_cost":4.0}}',),
            ]
        )
        with tempfile.TemporaryDirectory(prefix="sqlopt_mysql_compare_") as td:
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
                result = compare.compare_plan(cfg, "SELECT 1", "SELECT 1", Path(td))

        self.assertTrue(result["improved"])
        self.assertEqual(result["beforeSummary"]["totalCost"], 8.0)
        self.assertEqual(result["afterSummary"]["totalCost"], 4.0)

    def test_compare_semantics_returns_match_and_mismatch(self) -> None:
        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {}}
        with tempfile.TemporaryDirectory(prefix="sqlopt_mysql_semantics_") as td:
            cursor_match = _Cursor([(5,), (5,)])
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor_match), "pymysql")):
                match = compare.compare_semantics(cfg, "SELECT 1", "SELECT 1", Path(td))
            self.assertEqual(match["rowCount"]["status"], "MATCH")

            cursor_mismatch = _Cursor([(5,), (3,)])
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor_mismatch), "pymysql")):
                mismatch = compare.compare_semantics(cfg, "SELECT 1", "SELECT 2", Path(td))
            self.assertEqual(mismatch["rowCount"]["status"], "MISMATCH")

    def test_compare_semantics_handles_prepare_and_connectivity_fallback(self) -> None:
        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {}}
        with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(_Cursor([])), "pymysql")):
            result = compare.compare_semantics(cfg, "SELECT 1", "<if test='x'></if>", Path("."))
        self.assertEqual(result["reasonCategory"], "SQL_PREPARE_FAILED")

        cfg_fallback = {
            "db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"},
            "validate": {"allow_db_unreachable_fallback": True},
        }
        with patch(
            "sqlopt.platforms.mysql.compare._get_sql_connect",
            return_value=(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("can't connect to mysql server")), "pymysql"),
        ):
            fallback = compare.compare_semantics(cfg_fallback, "SELECT 1", "SELECT 1", Path("."))
        self.assertEqual(fallback["reasonCategory"], "DB_UNREACHABLE")
        self.assertEqual(fallback["rowCount"]["status"], "SKIPPED")

    def test_compare_semantics_tolerates_unsupported_timeout_setting(self) -> None:
        cfg = {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}, "validate": {}}
        cursor = _Cursor([(5,), (5,)], execute_errors=[RuntimeError("Unknown system variable 'MAX_EXECUTION_TIME'")])
        with tempfile.TemporaryDirectory(prefix="sqlopt_mysql_semantics_") as td:
            with patch("sqlopt.platforms.mysql.compare._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
                result = compare.compare_semantics(cfg, "SELECT 1", "SELECT 1", Path(td))
        self.assertTrue(result["checked"])
        self.assertEqual(result["rowCount"]["status"], "MATCH")


if __name__ == "__main__":
    unittest.main()
