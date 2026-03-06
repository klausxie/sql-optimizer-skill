from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from sqlopt.platforms.mysql import evidence


class _Cursor:
    def __init__(self, script: list[object], execute_errors: list[Exception] | None = None) -> None:
        self._script = list(script)
        self._execute_errors = list(execute_errors or [])
        self.executed: list[tuple[str, object | None]] = []

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: object | None = None) -> None:
        self.executed.append((sql, params))
        if self._execute_errors:
            raise self._execute_errors.pop(0)

    def fetchone(self):
        if not self._script:
            return None
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, list):
            return item
        return item

    def fetchall(self):
        if not self._script:
            return []
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


class MySqlEvidenceTest(unittest.TestCase):
    def test_check_db_connectivity_requires_dsn(self) -> None:
        result = evidence.check_db_connectivity({"db": {"platform": "mysql"}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "PREFLIGHT_DB_UNREACHABLE")

    def test_check_db_connectivity_reports_driver_missing(self) -> None:
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(None, None)):
            result = evidence.check_db_connectivity({"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "PREFLIGHT_DB_UNREACHABLE")

    def test_check_db_connectivity_succeeds(self) -> None:
        cursor = _Cursor([(1,)])
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            result = evidence.check_db_connectivity({"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}})
        self.assertTrue(result["ok"])

    def test_check_db_connectivity_tolerates_unsupported_timeout_setting(self) -> None:
        cursor = _Cursor([(1,)], execute_errors=[RuntimeError("Unknown system variable 'MAX_EXECUTION_TIME'")])
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            result = evidence.check_db_connectivity({"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}})
        self.assertTrue(result["ok"])

    def test_collect_sql_evidence_returns_static_only_without_dsn(self) -> None:
        evidence_row, summary = evidence.collect_sql_evidence({"db": {"platform": "mysql"}}, "SELECT 1")
        self.assertEqual(evidence_row["dbType"], "mysql")
        self.assertEqual(evidence_row["collectionMode"], "STATIC_ONLY")
        self.assertEqual(summary["summary"], "EXPLAIN skipped")

    def test_collect_sql_evidence_collects_metadata_and_explain(self) -> None:
        explain_payload = json.dumps({"query_block": {"cost_info": {"query_cost": "12.50"}}})
        cursor = _Cursor(
            [
                (explain_payload,),
                [
                    (None, None, "idx_users_name", None, "name"),
                    (None, None, "PRIMARY", None, "id"),
                ],
                [("users", 42)],
                [("users", "id", "bigint", "NO"), ("users", "name", "varchar", "YES")],
            ]
        )
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            evidence_row, summary = evidence.collect_sql_evidence(
                {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}},
                "SELECT id, name FROM users",
            )

        self.assertEqual(evidence_row["dbType"], "mysql")
        self.assertEqual(evidence_row["schema"], "demo")
        self.assertEqual(evidence_row["collectionMode"], "DB_CONNECTED")
        self.assertEqual(evidence_row["tables"], ["users"])
        self.assertEqual(evidence_row["indexes"][0]["index"], "idx_users_name")
        self.assertEqual(evidence_row["tableStats"][0]["estimatedRows"], 42)
        self.assertEqual(evidence_row["columns"][0]["column"], "id")
        self.assertEqual(summary["summary"], "query_cost=12.5")

    def test_collect_sql_evidence_records_metadata_error_without_blocking_explain(self) -> None:
        explain_payload = json.dumps({"query_block": {"cost_info": {"query_cost": "3.0"}}})
        cursor = _Cursor(
            [
                (explain_payload,),
                [("idx_users_name",)],
                RuntimeError("metadata failed"),
            ]
        )
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            evidence_row, summary = evidence.collect_sql_evidence(
                {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}},
                "SELECT id FROM users",
            )

        self.assertEqual(evidence_row["collectionMode"], "DB_CONNECTED")
        self.assertIn("metadataError", evidence_row)
        self.assertEqual(summary["summary"], "query_cost=3.0")

    def test_collect_sql_evidence_reports_explain_failure(self) -> None:
        cursor = _Cursor([RuntimeError("explain failed"), []])
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            evidence_row, summary = evidence.collect_sql_evidence(
                {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}},
                "SELECT id FROM users",
            )

        self.assertEqual(evidence_row["collectionMode"], "DB_CONNECTED")
        self.assertIn("explainError", evidence_row)
        self.assertEqual(summary["summary"], "EXPLAIN failed")

    def test_collect_sql_evidence_extracts_estimated_total_cost_from_new_json_schema(self) -> None:
        explain_payload = json.dumps({"query_plan": {"estimated_total_cost": 8.75}})
        cursor = _Cursor([(explain_payload,), [], [], []])
        with patch("sqlopt.platforms.mysql.evidence._get_sql_connect", return_value=(lambda **kwargs: _Conn(cursor), "pymysql")):
            evidence_row, summary = evidence.collect_sql_evidence(
                {"db": {"platform": "mysql", "dsn": "mysql://u:p@127.0.0.1:3306/demo"}},
                "SELECT 1",
            )

        self.assertEqual(evidence_row["planCost"], 8.75)
        self.assertEqual(summary["summary"], "query_cost=8.75")


if __name__ == "__main__":
    unittest.main()
