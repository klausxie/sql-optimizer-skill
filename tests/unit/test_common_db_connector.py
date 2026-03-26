"""Unit tests for DB connector plan normalization helpers."""

from sqlopt.common.db_connector import _extract_mysql_explain_payload, _extract_postgres_explain_payload


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
