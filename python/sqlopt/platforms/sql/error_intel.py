from __future__ import annotations

import re
from typing import Any

_UNKNOWN_COLUMN_PATTERNS = (
    re.compile(r"unknown column ['\"](?P<column>[^'\"]+)['\"]", re.IGNORECASE),
    re.compile(r"column ['\"]?(?P<column>[a-zA-Z0-9_.]+)['\"]? does not exist", re.IGNORECASE),
)
_UNKNOWN_TABLE_PATTERNS = (
    re.compile(r"table ['\"](?P<table>[^'\"]+)['\"] doesn't exist", re.IGNORECASE),
    re.compile(r"relation ['\"](?P<table>[^'\"]+)['\"] does not exist", re.IGNORECASE),
    re.compile(r"missing from-clause entry for table ['\"](?P<table>[^'\"]+)['\"]", re.IGNORECASE),
)


def parse_sql_runtime_error(raw_error: str) -> dict[str, Any]:
    text = str(raw_error or "").strip()
    if not text:
        return {}

    for pattern in _UNKNOWN_COLUMN_PATTERNS:
        match = pattern.search(text)
        if match:
            column = str(match.group("column") or "").strip()
            table = None
            if "." in column:
                table, column = column.rsplit(".", 1)
            return {
                "error_type": "MISSING_COLUMN",
                "table": table or None,
                "column": column or None,
                "original_error": text,
            }

    for pattern in _UNKNOWN_TABLE_PATTERNS:
        match = pattern.search(text)
        if match:
            return {
                "error_type": "MISSING_TABLE",
                "table": str(match.group("table") or "").strip() or None,
                "original_error": text,
            }

    return {
        "error_type": "SQL_RUNTIME_ERROR",
        "original_error": text,
    }


def normalize_table_names(raw_tables: Any) -> list[str]:
    out: list[str] = []
    for row in raw_tables or []:
        if isinstance(row, dict):
            name = str(row.get("table") or row.get("name") or "").strip()
        else:
            name = str(row or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def maybe_infer_table_for_column(
    details: dict[str, Any] | None,
    raw_tables: Any,
) -> dict[str, Any] | None:
    if not isinstance(details, dict):
        return details
    if str(details.get("error_type") or "").strip().upper() != "MISSING_COLUMN":
        return details
    if str(details.get("table") or "").strip():
        return details

    tables = normalize_table_names(raw_tables)
    column = str(details.get("column") or "").strip()
    if len(tables) == 1 and column and "." not in column:
        return {**details, "table": tables[0]}
    return details


def humanize_sql_runtime_error(details: dict[str, Any] | None) -> str | None:
    if not isinstance(details, dict):
        return None

    error_type = str(details.get("error_type") or "").strip().upper()
    table = str(details.get("table") or "").strip()
    column = str(details.get("column") or "").strip()
    original_error = str(details.get("original_error") or "").strip()

    if error_type == "MISSING_COLUMN" and column:
        qualified = f"{table}.{column}" if table else column
        return f"SQL references a missing column: {qualified}"
    if error_type == "MISSING_TABLE" and table:
        return f"SQL references a missing table: {table}"
    if original_error:
        return f"Semantic validation hit a database error: {original_error}"
    return None
