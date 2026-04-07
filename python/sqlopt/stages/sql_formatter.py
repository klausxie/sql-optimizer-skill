"""
SQL formatting utilities for patch generation.

Provides SQL formatting functions for creating patch-friendly layouts.
"""

from __future__ import annotations

import re

_MAJOR_SQL_BREAKS = (
    r"UNION\s+ALL",
    r"UNION",
    r"SELECT",
    r"FROM",
    r"WHERE",
    r"GROUP\s+BY",
    r"HAVING",
    r"ORDER\s+BY",
    r"LIMIT",
    r"OFFSET",
    r"SET",
    r"VALUES",
    r"LEFT\s+OUTER\s+JOIN",
    r"RIGHT\s+OUTER\s+JOIN",
    r"FULL\s+OUTER\s+JOIN",
    r"INNER\s+JOIN",
    r"LEFT\s+JOIN",
    r"RIGHT\s+JOIN",
    r"FULL\s+JOIN",
    r"JOIN",
)


def _split_sql_by_quotes(sql: str) -> list[tuple[str, bool]]:
    """Split SQL by quotes, returning (segment, is_quoted) pairs."""
    parts: list[tuple[str, bool]] = []
    if not sql:
        return parts
    buf: list[str] = []
    in_single = False
    in_double = False
    idx = 0
    while idx < len(sql):
        ch = sql[idx]
        if in_single:
            buf.append(ch)
            if ch == "'":
                if idx + 1 < len(sql) and sql[idx + 1] == "'":
                    # Escaped single quote inside SQL literal.
                    buf.append("'")
                    idx += 1
                else:
                    parts.append(("".join(buf), True))
                    buf = []
                    in_single = False
            idx += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                parts.append(("".join(buf), True))
                buf = []
                in_double = False
            idx += 1
            continue
        if ch == "'":
            if buf:
                parts.append(("".join(buf), False))
                buf = []
            buf.append(ch)
            in_single = True
            idx += 1
            continue
        if ch == '"':
            if buf:
                parts.append(("".join(buf), False))
                buf = []
            buf.append(ch)
            in_double = True
            idx += 1
            continue
        buf.append(ch)
        idx += 1
    if buf:
        parts.append(("".join(buf), in_single or in_double))
    return parts


def _format_unquoted_sql_segment(segment: str) -> str:
    """Format an unquoted SQL segment with proper line breaks."""
    text = " ".join(str(segment or "").split())
    if not text:
        return ""
    for pattern in _MAJOR_SQL_BREAKS:
        text = re.sub(rf"\s+({pattern})\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(AND|OR)\b", r"\n  \1", text, flags=re.IGNORECASE)
    return text.strip()


def format_sql_for_patch(sql: str) -> str:
    """Render SQL in a patch-friendly multi-line layout without changing semantics."""
    text = str(sql or "").strip()
    if not text:
        return ""
    out_parts: list[str] = []
    for segment, quoted in _split_sql_by_quotes(text):
        if quoted:
            out_parts.append(segment)
        else:
            out_parts.append(_format_unquoted_sql_segment(segment))
    formatted = "".join(out_parts)
    # Restore spacing that can be lost at quote boundaries after segment-wise formatting.
    formatted = re.sub(r"([=<>!])('(?:[^']|'')*')", r"\1 \2", formatted)
    formatted = re.sub(
        r"('(?:[^']|'')*')\s*(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT|OFFSET|FETCH)\b",
        r"\1\n\2",
        formatted,
        flags=re.IGNORECASE,
    )
    formatted = re.sub(
        r"('(?:[^']|'')*')\s*(AND|OR)\b",
        r"\1\n  \2",
        formatted,
        flags=re.IGNORECASE,
    )
    formatted = re.sub(r"[ \t]+\n", "\n", formatted)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    lines = [line.rstrip() for line in formatted.splitlines()]
    return "\n".join(lines).strip()


__all__ = [
    "format_sql_for_patch",
    "_split_sql_by_quotes",
    "_format_unquoted_sql_segment",
]
