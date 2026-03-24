"""BranchExpander - wraps XMLLanguageDriver + BranchGenerator for SQL branch expansion.

This module provides the BranchExpander class that expands MyBatis XML SQL
into execution branches using the XMLLanguageDriver for parsing and
BranchGenerator for generating branch combinations.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree
from dataclasses import dataclass
from typing import List


@dataclass
class ExpandedBranch:
    """Represents a single expanded SQL branch.

    Attributes:
        path_id: Unique identifier for this branch path (e.g., "branch_0", "branch_1").
        condition: The active condition that led to this branch, or None for default.
        expanded_sql: The rendered SQL string for this branch.
        is_valid: Whether this branch represents valid SQL.
    """

    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool


class BranchExpander:
    """Expands MyBatis XML SQL into branch combinations.

    This class wraps XMLLanguageDriver and BranchGenerator to parse MyBatis
    XML dynamic SQL and generate all possible execution branches.

    Usage:
        expander = BranchExpander(strategy="ladder", max_branches=50)
        branches = expander.expand(sql_text)
    """

    def __init__(self, strategy: str = "ladder", max_branches: int = 50) -> None:
        """Initialize with branch generation strategy.

        Args:
            strategy: Branch generation strategy.
                Options: "ladder", "all_combinations", "pairwise", "boundary"
            max_branches: Maximum number of branches to generate.
        """
        self.strategy = strategy
        self.max_branches = max_branches

    def expand(self, sql_text: str) -> List[ExpandedBranch]:
        """Expand SQL text into branch combinations.

        Parses the MyBatis XML SQL using XMLLanguageDriver and generates
        branch combinations using BranchGenerator.

        Args:
            sql_text: MyBatis XML SQL string with dynamic tags.

        Returns:
            List of ExpandedBranch objects representing all possible branches.
        """
        try:
            from sqlopt.stages.branching.branch_generator import BranchGenerator
            from sqlopt.stages.branching.xml_language_driver import XMLLanguageDriver

            sql_node = XMLLanguageDriver.create_sql_source(sql_text)
            generator = BranchGenerator(
                strategy=self.strategy,
                max_branches=self.max_branches,
            )
            branch_dicts = generator.generate(sql_node)
            return self._map_branches(branch_dicts)

        except (ValueError, RuntimeError, TypeError, xml.etree.ElementTree.ParseError) as e:
            logging.warning(f"Branch expansion failed, returning default branch: {e}")
            return [
                ExpandedBranch(
                    path_id="default",
                    condition=None,
                    expanded_sql=self._strip_xml_tags(sql_text),
                    is_valid=True,
                )
            ]

    def _map_branches(self, branch_dicts: List[dict]) -> List[ExpandedBranch]:
        """Map BranchGenerator output to ExpandedBranch list.

        Args:
            branch_dicts: List of branch dictionaries from BranchGenerator.

        Returns:
            List of ExpandedBranch objects.
        """
        if not branch_dicts:
            return [
                ExpandedBranch(
                    path_id="default",
                    condition=None,
                    expanded_sql="",
                    is_valid=True,
                )
            ]

        branches = []
        for branch_dict in branch_dicts:
            branch_id = branch_dict.get("branch_id", 0)
            active_conditions = branch_dict.get("active_conditions", [])
            sql = branch_dict.get("sql", "")

            path_id = f"branch_{branch_id}"
            condition = active_conditions[0] if active_conditions else None

            branches.append(
                ExpandedBranch(
                    path_id=path_id,
                    condition=condition,
                    expanded_sql=sql,
                    is_valid=True,
                )
            )

        return branches

    def _strip_xml_tags(self, sql: str) -> str:
        """Strip XML/MyBatis tags from SQL string.

        Args:
            sql: SQL string potentially containing XML tags.

        Returns:
            Clean SQL with all XML tags removed.
        """
        result = re.sub(r"<[^>]+>", "", sql)
        result = re.sub(r"\s+", " ", result)
        return result.strip()
