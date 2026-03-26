"""Unit tests for DB connector plan normalization helpers."""

from typing import Self

import pytest
from sqlopt.common.db_connector import (
    MySQLConnector,
    PostgreSQLConnector,
    _extract_mysql_explain_payload,
    _extract_postgres_explain_payload,
)


def test_extract_postgres_explain_payload_normalizes_wrapper() -> None:
    result = {
        "QUERY PLAN": [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 128.5,
                    "Actual Total Time": 9.75,
                }
            }
        ]
    }

    payload = _extract_postgres_explain_payload(result)

    assert payload["plan"]["Plan"]["Node Type"] == "Seq Scan"
    assert payload["estimated_cost"] == 128.5
    assert payload["actual_time_ms"] == 9.75


def test_extract_mysql_explain_payload_parses_json_column() -> None:
    result = {
        "EXPLAIN": (
            '{"query_block": {"cost_info": {"query_cost": "19.25"}, "table": {"rows_examined_per_scan": 320}}}'
        )
    }

    payload = _extract_mysql_explain_payload(result)

    assert payload["plan"]["query_block"]["table"]["rows_examined_per_scan"] == 320
    assert payload["estimated_cost"] == 19.25
    assert payload["actual_time_ms"] is None


class _FailingCursor:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, *_args, **_kwargs) -> None:
        raise self._error


class _FakeConnection:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.closed = False
        self.open = True
        self.rollback_calls = 0

    def cursor(self, *args, **kwargs) -> _FailingCursor:  # noqa: ARG002
        return _FailingCursor(self._error)

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_postgresql_execute_explain_rolls_back_after_failure(monkeypatch) -> None:
    connector = PostgreSQLConnector()
    connector._conn = _FakeConnection(RuntimeError("boom"))  # noqa: SLF001
    monkeypatch.setattr("sqlopt.common.db_connector._ensure_psycopg2", lambda: (object(), None))

    with pytest.raises(RuntimeError, match="boom"):
        connector.execute_explain("SELECT 1")

    assert connector._conn.rollback_calls == 1  # noqa: SLF001


def test_mysql_execute_query_rolls_back_after_failure() -> None:
    connector = MySQLConnector()
    connector._conn = _FakeConnection(RuntimeError("boom"))  # noqa: SLF001

    with pytest.raises(RuntimeError, match="boom"):
        connector.execute_query("SELECT 1")

    assert connector._conn.rollback_calls == 1  # noqa: SLF001
