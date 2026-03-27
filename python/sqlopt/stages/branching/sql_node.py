"""SqlNode abstract base class for MyBatis dynamic SQL processing.

This module provides the SqlNode interface, mirroring the MyBatis
org.apache.ibatis.scripting.xmltags.SqlNode interface.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Match

if TYPE_CHECKING:
    from sqlopt.stages.branching.dynamic_context import DynamicContext


_LOGICAL_KEYWORDS: tuple[str, ...] = ("AND ", "OR ")


def _can_follow_without_logical_operator(prev: str, curr: str) -> bool:
    """Return True when two fragments should be concatenated directly."""
    prev_stripped = prev.rstrip()
    curr_stripped = curr.lstrip()

    if not prev_stripped or not curr_stripped:
        return True

    if curr_stripped[0] in "),":
        return True

    if prev_stripped[-1] in "(=,":
        return True

    upper_prev = prev_stripped.upper()
    if curr_stripped[0] == "(" and (
        upper_prev.endswith(" IN")
        or upper_prev.endswith(" NOT IN")
        or upper_prev.endswith(" EXISTS")
        or upper_prev.endswith(" NOT EXISTS")
        or upper_prev.endswith(" VALUES")
    ):
        return True

    return False


def _strip_logical_prefix_if_needed(prev: str, curr: str) -> str | None:
    """Strip leading AND/OR from curr if prev ends with alnum.

    Returns the corrected curr string, or None if no stripping needed.
    """
    if not prev or not curr:
        return None
    prev_last = prev.strip()[-1:] if prev.strip() else ""
    if not prev_last.isalnum():
        return None
    curr_upper = curr.upper()
    for keyword in _LOGICAL_KEYWORDS:
        if curr_upper.startswith(keyword.upper()):
            return curr[len(keyword) :]
    return None


class SqlNode(ABC):
    """Abstract base class for MyBatis SqlNode.

    SqlNode represents a node in the MyBatis XML mapping that can
    process dynamic content. Each SqlNode implementation handles
    a specific type of dynamic SQL element (e.g., if, foreach, where).

    The apply() method returns True if content was appended to the context,
    False otherwise. This allows for conditional SQL generation.
    """

    @abstractmethod
    def apply(self, context: DynamicContext) -> bool:
        """Apply this SqlNode to the context.

        Args:
            context: The DynamicContext to apply this node to.

        Returns:
            True if content was appended to the context, False otherwise.
        """


class StaticTextSqlNode(SqlNode):
    """Static text SqlNode that directly appends text to context.

    This class mirrors MyBatis StaticTextSqlNode which handles static
    text content in dynamic SQL templates without any variable substitution.
    """

    def __init__(self, text: str) -> None:
        """Initialize StaticTextSqlNode with text content.

        Args:
            text: The static text content to append.
        """
        self.text: str = text

    def apply(self, context: DynamicContext) -> bool:
        """Apply this StaticTextSqlNode to the context.

        Args:
            context: The DynamicContext to append text to.

        Returns:
            True always, as static text is always appended.
        """
        context.append_sql(self.text)
        return True


class TextSqlNode(SqlNode):
    """Text SqlNode that handles ${} placeholder substitution.

    This class mirrors MyBatis TextSqlNode which handles dynamic text
    with ${} variable placeholders. It replaces ${var} patterns with
    values from the context bindings.

    Note: Does NOT handle #{} parameter placeholders (those are handled
    separately by the parameter mapping system).
    """

    # Regex pattern to match ${...} placeholders
    _PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, text: str) -> None:
        """Initialize TextSqlNode with text content.

        Args:
            text: The text content containing ${} placeholders.
        """
        self.text: str = text

    def apply(self, context: DynamicContext) -> bool:
        """Apply this TextSqlNode to the context.

        Replaces ${var} placeholders with values from context.bindings.

        Args:
            context: The DynamicContext containing bindings.

        Returns:
            True always, as text processing always produces output.
        """
        result = self._PLACEHOLDER_PATTERN.sub(lambda match: self._resolve_placeholder(match, context), self.text)
        context.append_sql(result)
        return True

    @staticmethod
    def _resolve_placeholder(match: Match[str], context: DynamicContext) -> str:
        """Resolve a ${} placeholder to its binding value.

        Args:
            match: The regex match object.
            context: The DynamicContext containing bindings.

        Returns:
            The resolved value as a string, or empty string if not found.
        """
        var_name = match.group(1)
        value = context.bindings.get(var_name)
        if value is None:
            return ""
        return str(value)


class MixedSqlNode(SqlNode):
    """Mixed SqlNode that contains multiple child SqlNodes.

    This class mirrors MyBatis MixedSqlNode which holds a list of
    SqlNode instances and applies them in sequence. It's used as a
    container for combining multiple SQL nodes into a single node
    that can be processed together.
    """

    def __init__(self, contents: list[SqlNode]) -> None:
        """Initialize MixedSqlNode with a list of child SqlNodes.

        Args:
            contents: A list of SqlNode instances to apply in sequence.
        """
        self.contents: list[SqlNode] = contents

    def apply(self, context: DynamicContext) -> bool:
        result = False
        for node in self.contents:
            if node.apply(context):
                result = True
                if len(context.sql_fragments) >= 2:
                    prev = context.sql_fragments[-2]
                    curr = context.sql_fragments[-1]
                    stripped = _strip_logical_prefix_if_needed(prev, curr)
                    if stripped is not None:
                        context.sql_fragments[-1] = stripped
        return result


class IfSqlNode(SqlNode):
    """If SqlNode that handles conditional SQL inclusion.

    This class mirrors MyBatis IfSqlNode which represents the <if>
    test attribute in MyBatis dynamic SQL.

    Supports conditional evaluation via active_conditions set.
    """

    def __init__(self, test: str, contents: SqlNode, active_conditions: set | None = None) -> None:
        """Initialize IfSqlNode with test expression and contents.

        Args:
            test: The OGNL expression string to evaluate (stored only).
            contents: The SqlNode containing the conditional SQL content.
            active_conditions: Set of conditions that should evaluate to TRUE.
        """
        self.test: str = test
        self.contents: SqlNode = contents
        self.active_conditions: set = active_conditions or set()

    def apply(self, context: DynamicContext) -> bool:
        """Apply this IfSqlNode to the context.

        Only applies contents if test condition is in active_conditions.

        Args:
            context: The DynamicContext to apply contents to.

        Returns:
            The result of applying contents to context.
        """
        # Check if this condition is active (should be applied)
        if self.test in self.active_conditions:
            return self.contents.apply(context)
        return False


class WhenSqlNode(IfSqlNode):
    """When SqlNode for <choose><when> branch.

    This class mirrors MyBatis ChooseSqlNode.WhenSqlNode which represents
    the <when> test attribute in MyBatis dynamic SQL <choose> element.

    Inherits from IfSqlNode and adds the test expression handling.
    """

    def __init__(self, test: str, contents: SqlNode, active_conditions: set | None = None) -> None:
        """Initialize WhenSqlNode with test expression and contents.

        Args:
            test: The OGNL expression string to evaluate (stored only).
            contents: The SqlNode containing the conditional SQL content.
            active_conditions: Set of conditions that should evaluate to TRUE.
        """
        super().__init__(test, contents, active_conditions)


class OtherwiseSqlNode(StaticTextSqlNode):
    """Otherwise SqlNode for <choose><otherwise> branch.

    This class mirrors MyBatis ChooseSqlNode.OtherwiseSqlNode which represents
    the <otherwise> element in MyBatis dynamic SQL <choose> element.

    Inherits from StaticTextSqlNode as it contains static SQL content.
    """

    def __init__(self, contents: SqlNode) -> None:
        """Initialize OtherwiseSqlNode with contents.

        Args:
            contents: The SqlNode containing the fallback SQL content.
        """
        # Initialize with empty text; content comes from contents node
        super().__init__("")
        self.contents: SqlNode = contents

    def apply(self, context: DynamicContext) -> bool:
        """Apply this OtherwiseSqlNode to the context.

        Args:
            context: The DynamicContext to apply contents to.

        Returns:
            The result of applying contents to context.
        """
        return self.contents.apply(context)


class ChooseSqlNode(SqlNode):
    """Choose SqlNode that handles <choose> (if-else) SQL inclusion.

    This class mirrors MyBatis ChooseSqlNode which represents the <choose>
    element in MyBatis dynamic SQL. It contains multiple <when> branches
    and an optional <otherwise> branch.

    Per requirements, this implementation does NOT evaluate test expressions
    for mutual exclusivity. All when nodes are applied in sequence (the
    branch generator handles mutual exclusion logic).
    """

    def __init__(self, if_sql_nodes: list[WhenSqlNode], default_sql_node: OtherwiseSqlNode | None) -> None:
        """Initialize ChooseSqlNode with when branches and optional otherwise.

        Args:
            if_sql_nodes: List of WhenSqlNode branches to evaluate.
            default_sql_node: Optional OtherwiseSqlNode for the fallback case.
        """
        self.if_sql_nodes: list[WhenSqlNode] = if_sql_nodes
        self.default_sql_node: OtherwiseSqlNode | None = default_sql_node

    def apply(self, context: DynamicContext) -> bool:
        """Apply this ChooseSqlNode to the context.

        Applies the first when branch whose condition is active.
        If no when matches, applies otherwise branch.

        Args:
            context: The DynamicContext to apply contents to.

        Returns:
            True if any branch appended content, False otherwise.
        """
        # Try each when branch - first match wins (mutex)
        for when_node in self.if_sql_nodes:
            if when_node.test in when_node.active_conditions:
                if when_node.apply(context):
                    return True

        # If no when matched, try otherwise
        if self.default_sql_node is not None:
            if self.default_sql_node.apply(context):
                return True

        return False


class TrimSqlNode(SqlNode):
    """Trim SqlNode that handles prefix/suffix trimming.

    Mirrors MyBatis TrimSqlNode which handles prefix/suffix addition
    and prefix/suffix override (removal of AND/OR at start/end).
    """

    def __init__(
        self,
        contents: SqlNode,
        prefix: str = "",
        suffix: str = "",
        prefix_overrides: list[str] | None = None,
        suffix_overrides: list[str] | None = None,
    ) -> None:
        self.contents = contents
        self.prefix = prefix
        self.suffix = suffix
        self.prefix_overrides = prefix_overrides or []
        self.suffix_overrides = suffix_overrides or []

    def apply(self, context: DynamicContext) -> bool:
        """Apply this TrimSqlNode by processing child nodes and wrapping with prefix/suffix."""
        from sqlopt.stages.branching.dynamic_context import DynamicContext as DC

        temp_context = DC()
        temp_context.bindings = context.bindings
        temp_context.sql_fragments = []

        if not self.contents.apply(temp_context):
            return False

        sql = self._join_fragments(temp_context.sql_fragments)
        sql = self._apply_prefix_overrides(sql)
        sql = self._apply_suffix_overrides(sql)
        sql = self._wrap_with_prefix_suffix(sql)

        if sql.strip():
            context.append_sql(sql)
            return True
        return False

    def _join_fragments(self, fragments: list[str]) -> str:
        """Join SQL fragments with proper AND/OR spacing."""
        if len(fragments) <= 1:
            return "".join(fragments).strip()

        fixed_fragments = [fragments[0]]
        for i in range(1, len(fragments)):
            curr = fragments[i]
            prev = fixed_fragments[-1]
            curr = self._maybe_insert_logical_operator(prev, curr)
            fixed_fragments.append(curr)
        return "".join(fixed_fragments).strip()

    def _maybe_insert_logical_operator(self, prev: str, curr: str) -> str:
        """Determine if and what logical operator to insert between two fragments."""
        if not prev or not curr:
            return curr

        needs_and = self._needs_logical_connection(prev)
        curr_starts_logical = curr.strip().upper().startswith(_LOGICAL_KEYWORDS)
        prev_starts_logical = prev.strip().upper().startswith(_LOGICAL_KEYWORDS)

        if prev.strip().upper().endswith(("AND", "OR", "AND ", "OR ")):
            return " " + curr
        if curr_starts_logical and needs_and:
            return " " + curr
        if prev_starts_logical and needs_and and not _can_follow_without_logical_operator(prev, curr):
            return " AND " + curr
        return self._handle_needs_and_case(prev, curr, needs_and, curr_starts_logical)

    @staticmethod
    def _needs_logical_connection(fragment: str) -> bool:
        """Return True if fragment ends with a character that needs logical connection."""
        last_char = fragment.strip()[-1:] if fragment.strip() else ""
        return last_char.isalnum() or last_char == "}"

    @staticmethod
    def _handle_needs_and_case(prev: str, curr: str, needs_and: bool, curr_starts_logical: bool) -> str:
        """Handle the case where prev fragment needs AND connection to curr."""
        if not needs_and or curr_starts_logical:
            return curr
        curr_first = curr.strip()[:1] if curr.strip() else ""
        if _can_follow_without_logical_operator(prev, curr):
            if curr_first.isalnum() and not prev.endswith((" ", "\t", "\n")):
                return " " + curr
        elif curr_first.isalnum() or curr_first in "#(":
            return " AND " + curr
        return curr

    def _apply_prefix_overrides(self, sql: str) -> str:
        """Remove leading AND/OR based on prefix_overrides."""
        for override in self.prefix_overrides:
            if sql.upper().startswith(override.upper()):
                return sql[len(override) :]
        return sql

    def _apply_suffix_overrides(self, sql: str) -> str:
        """Remove trailing content based on suffix_overrides."""
        for override in self.suffix_overrides:
            if sql.upper().endswith(override.upper()):
                return sql[: -len(override)]
        return sql

    def _wrap_with_prefix_suffix(self, sql: str) -> str:
        """Apply prefix and suffix wrapping with proper spacing."""
        if not sql.strip():
            return sql
        prefix = self.prefix
        suffix = self.suffix
        if prefix and prefix[0].isalpha():
            prefix = " " + prefix
        if suffix and suffix[-1].isalpha():
            suffix = suffix + " "
        return prefix + sql + suffix


class WhereSqlNode(TrimSqlNode):
    """Where SqlNode that handles <where> element.

    Mirrors MyBatis WhereSqlNode which adds WHERE keyword and removes
    leading AND/OR from the first condition.
    """

    def __init__(self, contents: SqlNode) -> None:
        super().__init__(
            contents,
            prefix=" WHERE ",
            prefix_overrides=["AND ", "OR ", "AND\n", "OR\n"],
        )


class SetSqlNode(TrimSqlNode):
    """Set SqlNode that handles <set> element.

    Mirrors MyBatis SetSqlNode which adds SET keyword and removes
    trailing comma from the last assignment.
    """

    def __init__(self, contents: SqlNode) -> None:
        """Initialize SetSqlNode with contents.

        Args:
            contents: The SqlNode containing the SET clause content.
        """
        super().__init__(
            contents,
            prefix="SET ",
            suffix_overrides=[","],
        )


class ForEachSqlNode(SqlNode):
    """ForEach SqlNode that handles collection iteration.

    Mirrors MyBatis ForEachSqlNode which handles iterating over collections
    for IN clauses and batch inserts.
    """

    def __init__(
        self,
        collection: str = "",
        item: str = "",
        index: str = "",
        open: str = "",
        close: str = "",
        separator: str = "",
        contents: SqlNode | None = None,
        sample_size: int = 2,
    ) -> None:
        self.collection = collection
        self.item = item
        self.index = index
        self.open = open
        self.close = close
        self.separator = separator
        self.contents = contents
        self.sample_size = max(1, sample_size)

    def apply(self, context: DynamicContext) -> bool:
        if self.contents is None:
            return False

        from sqlopt.stages.branching.dynamic_context import DynamicContext as DC

        rendered_items: list[str] = []
        for offset in range(self.sample_size):
            temp_context = DC()
            temp_context.bindings = dict(context.bindings)
            temp_context.sql_fragments = []

            if self.item:
                temp_context.bind(self.item, f"{self.item}_{offset}")
            if self.index:
                temp_context.bind(self.index, offset)

            self.contents.apply(temp_context)
            fragment = " ".join(temp_context.get_sql().split())
            if fragment:
                rendered_items.append(fragment)

        if not rendered_items:
            rendered = f"{self.open}{self.close}"
            if rendered:
                context.append_sql(rendered)
                return True
            return False

        rendered = self.open + self.separator.join(rendered_items) + self.close
        context.append_sql(rendered)
        return True


class VarDeclSqlNode(SqlNode):
    def __init__(self, name: str, expression: str) -> None:
        self.name = name
        self.expression = expression

    def apply(self, context: DynamicContext) -> bool:
        context.bind(self.name, self.expression)
        return True


class IncludeSqlNode(SqlNode):
    def __init__(self, refid: str, fragment_registry) -> None:
        self.refid = refid
        self.fragment_registry = fragment_registry

    def apply(self, context: DynamicContext) -> bool:
        fragment = self.fragment_registry.lookup(self.refid)
        if fragment:
            return fragment.apply(context)
        return False
