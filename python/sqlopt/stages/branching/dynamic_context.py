"""DynamicContext for MyBatis dynamic SQL processing.

This module provides the DynamicContext class, mirroring the MyBatis
org.apache.ibatis.scripting.xmltags.DynamicContext to store bindings
and accumulate SQL fragments during dynamic SQL processing.
"""

from __future__ import annotations

from typing import Any


class DynamicContext:
    """Context for dynamic SQL processing.

    DynamicContext stores variable bindings and accumulates SQL fragments
    during the processing of dynamic SQL nodes. It mirrors the MyBatis
    DynamicContext class, which uses a List to store SQL fragments that
    are joined together at the end.

    Attributes:
        bindings: Dictionary storing variable bindings for parameter access.
        sql_fragments: List storing SQL fragments as they are appended.
    """

    def __init__(self) -> None:
        """Initialize an empty DynamicContext."""
        self.bindings: dict[str, Any] = {}
        self.sql_fragments: list[str] = []

    def bind(self, name: str, value: Any) -> None:
        """Bind a variable to the context.

        Args:
            name: The variable name to bind.
            value: The value to bind to the name.
        """
        self.bindings[name] = value

    def append_sql(self, sql: str) -> None:
        """Append a SQL fragment to the context.

        Args:
            sql: The SQL fragment to append.
        """
        self.sql_fragments.append(sql)

    @staticmethod
    def _last_non_space_char(s: str) -> str:
        """Get the last non-whitespace character of a string."""
        for c in reversed(s):
            if c not in " \t\n":
                return c
        return ""

    def get_sql(self) -> str:
        """Get the complete SQL string.

        Joins accumulated SQL fragments with smart spacing.
        Avoids adding spaces around commas to prevent ", ," issues.

        Returns:
            The complete SQL string.
        """
        if not self.sql_fragments:
            return ""

        parts = []
        for i, frag in enumerate(self.sql_fragments):
            if not frag:
                continue
            if i == 0:
                parts.append(frag)
                continue

            prev = parts[-1] if parts else ""
            curr = frag

            # Use last non-whitespace char for smart spacing
            prev_last = self._last_non_space_char(prev)
            curr_first = curr[0] if curr else ""

            if prev_last == ",":
                # prev ends with comma, don't add space
                parts.append(curr)
            elif prev_last.isalnum() and curr_first == ",":
                # prev ends with alnum, curr starts with comma, don't add space
                parts.append(curr)
            elif prev_last.isalnum() and curr_first.isalnum():
                # Both alphanumeric, add space
                parts.append(" " + curr)
            elif prev_last in ("(", "[") and curr_first == " ":
                # Trim space after parenthesis
                parts.append(curr.lstrip())
            else:
                # Default: add space
                parts.append(" " + curr if curr else "")

        return "".join(parts)
