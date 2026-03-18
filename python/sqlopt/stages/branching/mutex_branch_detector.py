"""Mutex branch detector for ChooseSqlNode mutual exclusion handling.

This module provides the MutexBranchDetector class which detects and
generates mutually exclusive branches for MyBatis <choose> nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from sqlopt.stages.branching.sql_node import (
        ChooseSqlNode,
        WhenSqlNode,
        OtherwiseSqlNode,
    )
    from sqlopt.stages.branching.branch_context import BranchContext


class MutexBranchDetector:
    """Detects and generates mutually exclusive branches for choose nodes.

    In MyBatis <choose> nodes, the <when> branches are mutually exclusive -
    only one when clause should be applied, plus optionally an <otherwise>.

    This detector generates N+1 branches for a choose with N when nodes
    and an optional otherwise: one branch for each when, plus one for otherwise.
    """

    def detect_choose_branches(
        self,
        choose_node: ChooseSqlNode,
    ) -> List[List[str]]:
        """Generate mutually exclusive branches for a choose node.

        Args:
            choose_node: The ChooseSqlNode to analyze.

        Returns:
            List of branch definitions. Each branch is a list of condition
            strings that should be TRUE. For choose nodes:
            - Each when node generates one branch with its test condition
            - If there's an otherwise, it generates one branch (empty conditions)
        """
        branches: List[List[str]] = []

        # Generate one branch per when node
        for when_node in choose_node.if_sql_nodes:
            if when_node.test:
                branches.append([when_node.test])
            else:
                # when without test - matches like otherwise
                branches.append([])

        # If there's an otherwise, add it as a separate branch
        # (empty conditions = all previous conditions false)
        if choose_node.default_sql_node is not None:
            branches.append([])  # otherwise branch - no conditions active

        return branches

    def generate_branch_contexts(
        self,
        choose_node: ChooseSqlNode,
        branch_index: int,
    ) -> BranchContext | None:
        """Generate a BranchContext for a specific branch index.

        Args:
            choose_node: The ChooseSqlNode to generate context for.
            branch_index: Which branch to generate (0 to N for N when nodes,
                         N+1 for otherwise).

        Returns:
            BranchContext with active conditions set, or None if invalid index.
        """
        from sqlopt.stages.branching.branch_context import BranchContext

        when_count = len(choose_node.if_sql_nodes)
        has_otherwise = choose_node.default_sql_node is not None

        # Validate branch_index
        max_branch = when_count
        if has_otherwise:
            max_branch += 1

        if branch_index < 0 or branch_index >= max_branch:
            return None

        context = BranchContext(branch_id=branch_index)

        if branch_index < when_count:
            # This is a when branch - activate its condition
            when_node = choose_node.if_sql_nodes[branch_index]
            if when_node.test:
                context.activate_condition(when_node.test)
        # Otherwise branch has no active conditions (all false)

        return context

    def get_branch_count(self, choose_node: ChooseSqlNode) -> int:
        """Get the total number of branches for a choose node.

        Args:
            choose_node: The ChooseSqlNode to analyze.

        Returns:
            Number of mutually exclusive branches.
        """
        count = len(choose_node.if_sql_nodes)
        if choose_node.default_sql_node is not None:
            count += 1  # otherwise
        return count

    def is_mutex_node(self, node) -> bool:
        """Check if a node is a mutex (mutually exclusive) type.

        Args:
            node: The SqlNode to check.

        Returns:
            True if the node is ChooseSqlNode.
        """
        from sqlopt.stages.branching.sql_node import ChooseSqlNode

        return isinstance(node, ChooseSqlNode)
