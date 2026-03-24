from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlopt.stages.branching.fragment_registry import FragmentRegistry
    from sqlopt.stages.branching.sql_node import SqlNode


@dataclass(frozen=True)
class BranchDimension:
    condition: str
    required_conditions: tuple[str, ...]
    sql_fragment: str
    depth: int
    mutex_group: str | None = None

    @property
    def activation_conditions(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for condition in (*self.required_conditions, self.condition):
            if condition and condition not in seen:
                seen.add(condition)
                ordered.append(condition)
        return tuple(ordered)


class DimensionExtractor:
    """Extract branch planning dimensions from a SqlNode tree."""

    def __init__(self) -> None:
        self._choose_counter = count()

    def extract(self, sql_node: SqlNode) -> list[BranchDimension]:
        dimensions: list[BranchDimension] = []
        self._extract_recursive(
            sql_node,
            dimensions,
            parent_conditions=(),
            include_stack=set(),
        )
        return dimensions

    def _extract_recursive(
        self,
        sql_node: SqlNode,
        dimensions: list[BranchDimension],
        parent_conditions: tuple[str, ...],
        include_stack: set[str],
    ) -> None:
        from sqlopt.stages.branching.sql_node import (
            ChooseSqlNode,
            ForEachSqlNode,
            IfSqlNode,
            IncludeSqlNode,
            MixedSqlNode,
            SetSqlNode,
            TrimSqlNode,
            WhereSqlNode,
        )

        if isinstance(sql_node, IfSqlNode):
            if sql_node.test:
                dimensions.append(
                    BranchDimension(
                        condition=sql_node.test,
                        required_conditions=parent_conditions,
                        sql_fragment=self._collect_sql_fragment(
                            sql_node.contents,
                            include_stack=set(include_stack),
                        ),
                        depth=len(parent_conditions),
                    )
                )
                next_parent_conditions = (*parent_conditions, sql_node.test)
            else:
                next_parent_conditions = parent_conditions
            self._extract_recursive(
                sql_node.contents,
                dimensions,
                next_parent_conditions,
                include_stack,
            )
            return

        if isinstance(sql_node, ChooseSqlNode):
            choose_group = f"choose_{next(self._choose_counter)}"
            for when_node in sql_node.if_sql_nodes:
                if when_node.test:
                    dimensions.append(
                        BranchDimension(
                            condition=when_node.test,
                            required_conditions=parent_conditions,
                            sql_fragment=self._collect_sql_fragment(
                                when_node.contents,
                                include_stack=set(include_stack),
                            ),
                            depth=len(parent_conditions),
                            mutex_group=choose_group,
                        )
                    )
                    next_parent_conditions = (*parent_conditions, when_node.test)
                else:
                    next_parent_conditions = parent_conditions
                self._extract_recursive(
                    when_node.contents,
                    dimensions,
                    next_parent_conditions,
                    include_stack,
                )
            if sql_node.default_sql_node is not None:
                dimensions.append(
                    BranchDimension(
                        condition="",
                        required_conditions=parent_conditions,
                        sql_fragment=self._collect_sql_fragment(
                            sql_node.default_sql_node.contents,
                            include_stack=set(include_stack),
                        ),
                        depth=len(parent_conditions),
                        mutex_group=choose_group,
                    )
                )
                self._extract_recursive(
                    sql_node.default_sql_node.contents,
                    dimensions,
                    parent_conditions,
                    include_stack,
                )
            return

        if isinstance(sql_node, IncludeSqlNode):
            if not sql_node.fragment_registry or sql_node.refid in include_stack:
                return
            fragment = sql_node.fragment_registry.lookup(sql_node.refid)
            if fragment is None:
                return
            next_stack = set(include_stack)
            next_stack.add(sql_node.refid)
            self._extract_recursive(
                fragment,
                dimensions,
                parent_conditions,
                next_stack,
            )
            return

        if isinstance(sql_node, MixedSqlNode):
            for child in sql_node.contents:
                self._extract_recursive(
                    child,
                    dimensions,
                    parent_conditions,
                    include_stack,
                )
            return

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            self._extract_recursive(
                sql_node.contents,
                dimensions,
                parent_conditions,
                include_stack,
            )
            return

        if isinstance(sql_node, ForEachSqlNode) and sql_node.contents:
            self._extract_recursive(
                sql_node.contents,
                dimensions,
                parent_conditions,
                include_stack,
            )

    def _collect_sql_fragment(
        self,
        sql_node: SqlNode,
        include_stack: set[str],
    ) -> str:
        from sqlopt.stages.branching.sql_node import (
            ChooseSqlNode,
            ForEachSqlNode,
            IfSqlNode,
            IncludeSqlNode,
            MixedSqlNode,
            OtherwiseSqlNode,
            SetSqlNode,
            StaticTextSqlNode,
            TextSqlNode,
            TrimSqlNode,
            VarDeclSqlNode,
            WhereSqlNode,
        )

        if isinstance(sql_node, (StaticTextSqlNode, TextSqlNode)):
            return sql_node.text

        if isinstance(sql_node, VarDeclSqlNode):
            return sql_node.expression

        if isinstance(sql_node, (IfSqlNode, OtherwiseSqlNode)):
            return self._collect_sql_fragment(sql_node.contents, include_stack)

        if isinstance(sql_node, IncludeSqlNode):
            if not sql_node.fragment_registry or sql_node.refid in include_stack:
                return ""
            fragment = sql_node.fragment_registry.lookup(sql_node.refid)
            if fragment is None:
                return ""
            next_stack = set(include_stack)
            next_stack.add(sql_node.refid)
            return self._collect_sql_fragment(fragment, next_stack)

        if isinstance(sql_node, MixedSqlNode):
            return " ".join(
                part
                for part in (
                    self._collect_sql_fragment(child, include_stack)
                    for child in sql_node.contents
                )
                if part
            )

        if isinstance(sql_node, (TrimSqlNode, WhereSqlNode, SetSqlNode)):
            return self._collect_sql_fragment(sql_node.contents, include_stack)

        if isinstance(sql_node, ForEachSqlNode):
            inner = ""
            if sql_node.contents:
                inner = self._collect_sql_fragment(sql_node.contents, include_stack)
            return f"{sql_node.open} {inner} {sql_node.close}".strip()

        if isinstance(sql_node, ChooseSqlNode):
            parts = [
                self._collect_sql_fragment(when_node.contents, include_stack)
                for when_node in sql_node.if_sql_nodes
            ]
            if sql_node.default_sql_node is not None:
                parts.append(
                    self._collect_sql_fragment(
                        sql_node.default_sql_node.contents,
                        include_stack,
                    )
                )
            return " ".join(part for part in parts if part)

        return ""
