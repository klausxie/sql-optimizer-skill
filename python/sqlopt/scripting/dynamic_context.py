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

    def get_sql(self) -> str:
        """Get the complete SQL string.

        Joins all accumulated SQL fragments into a single string with spaces
        between fragments to prevent concatenation issues.

        Returns:
            The complete SQL string.
        """
        if not self.sql_fragments:
            return ""

        # Join fragments with space, then normalize whitespace
        joined = " ".join(self.sql_fragments)
        # Normalize: collapse multiple spaces to single space
        return " ".join(joined.split())
