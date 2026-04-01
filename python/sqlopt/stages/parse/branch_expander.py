"""BranchExpander - wraps XMLLanguageDriver + BranchGenerator for SQL branch expansion.

This module provides the BranchExpander class that expands MyBatis XML SQL
into execution branches using the XMLLanguageDriver for parsing and
BranchGenerator for generating branch combinations.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree
from dataclasses import dataclass, field
from typing import Any, List

from sqlopt.common.defaults import DEFAULT_MAX_BRANCHES
from sqlopt.contracts.init import FieldDistribution
from sqlopt.stages.branching.branch_validator import BranchValidator
from sqlopt.stages.branching.fragment_registry import FragmentRegistry


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
    risk_flags: list[str] = field(default_factory=list)
    active_conditions: list[str] = field(default_factory=list)
    risk_score: float | None = None
    score_reasons: list[str] = field(default_factory=list)
    branch_type: str | None = None


def count_conditions_from_sql(sql_text: str) -> int:
    """Count unique <if test="..."> conditions in raw SQL text.

    Fast heuristic: just count <if test= patterns without parsing.
    """
    import re

    if not sql_text:
        return 0
    pattern = r'<if\s+test\s*=\s*["\']([^"\']+)["\']'
    matches = re.findall(pattern, sql_text, re.IGNORECASE)
    return len(set(matches))


def adaptive_max_branches(
    cond_count: int,
    base: int | None = None,
    cap: int | None = None,
) -> tuple[int, str]:
    """Determine max branches and strategy based on condition count.

    Formula:
        - cond_count <= 0                             -> (1, "all_combinations")
        - 2**cond_count <= BASE                       -> (2**cond_count, "all_combinations")
        - otherwise                                   -> (max(BASE, 2**(cond_count-1), CAP), "ladder")

    Args:
        cond_count: Number of conditions.
        base: Override BASE (defaults to DEFAULT_MAX_BRANCHES).
        cap:  Override CAP (defaults to MAX_CAP).
    """
    from sqlopt.common.defaults import DEFAULT_MAX_BRANCHES, MAX_CAP

    effective_base = base if base is not None else DEFAULT_MAX_BRANCHES
    effective_cap = cap if cap is not None else MAX_CAP

    if cond_count <= 0:
        return (1, "all_combinations")
    theoretical = 2**cond_count
    if theoretical <= effective_base:
        return (theoretical, "all_combinations")
    adaptive_cap = min(max(effective_base, 2 ** (cond_count - 1)), effective_cap)
    return (adaptive_cap, "ladder")


class BranchExpander:
    """Expands MyBatis XML SQL into branch combinations.

    This class wraps XMLLanguageDriver and BranchGenerator to parse MyBatis
    XML dynamic SQL and generate all possible execution branches.

    Usage:
        expander = BranchExpander(strategy="ladder", max_branches=100)
        branches = expander.expand(sql_text)
    """

    def __init__(
        self,
        strategy: str = "ladder",
        max_branches: int = DEFAULT_MAX_BRANCHES,
        fragments: FragmentRegistry | None = None,
        table_metadata: dict[str, dict[str, Any]] | None = None,
        field_distributions: dict[str, list[FieldDistribution]] | None = None,
    ) -> None:
        """Initialize with branch generation strategy.

        Args:
            strategy: Branch generation strategy.
                Options: "ladder", "all_combinations", "each", "boundary"
            max_branches: Maximum number of branches to generate.
        """
        self.strategy = strategy
        self.max_branches = max_branches
        self.fragments = fragments
        self.table_metadata = table_metadata or {}
        self.field_distributions = field_distributions or {}

    def expand(
        self,
        sql_text: str,
        default_namespace: str | None = None,
        max_branches_override: int | None = None,
    ) -> List[ExpandedBranch]:
        """Expand SQL text into branch combinations."""
        try:
            from sqlopt.stages.branching.branch_generator import BranchGenerator
            from sqlopt.stages.branching.xml_language_driver import XMLLanguageDriver

            sql_node = XMLLanguageDriver.create_sql_source(
                sql_text,
                fragments=self.fragments,
                default_namespace=default_namespace,
            )
            cond_count = BranchGenerator.count_if_nodes(sql_node)
            max_br, adaptive_strategy = adaptive_max_branches(cond_count)
            if max_branches_override is not None:
                effective_max = max_branches_override
                effective_strategy = self.strategy
            elif cond_count == 0:
                effective_max = self.max_branches
                effective_strategy = self.strategy
            else:
                effective_max = min(max_br, self.max_branches)
                # Only override strategy if user didn't explicitly choose a non-ladder strategy
                effective_strategy = "ladder" if self.strategy == "ladder" else adaptive_strategy
            generator = BranchGenerator(
                strategy=effective_strategy,
                max_branches=effective_max,
                table_metadata=self.table_metadata,
                field_distributions=self.field_distributions,
            )
            branch_dicts = generator.generate(sql_node)
            self.theoretical_branches = generator.theoretical_branches
            return self._map_branches(branch_dicts)

        except (
            AttributeError,
            ValueError,
            RuntimeError,
            TypeError,
            xml.etree.ElementTree.ParseError,
        ) as e:
            logging.warning(f"Branch expansion failed, returning default branch: {e}")
            self.theoretical_branches = 1
            return [
                ExpandedBranch(
                    path_id="default",
                    condition=None,
                    expanded_sql=self._strip_xml_tags(sql_text),
                    is_valid=True,
                )
            ]

    @staticmethod
    def _map_branches(branch_dicts: List[dict]) -> List[ExpandedBranch]:
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
            risk_flags = branch_dict.get("risk_flags", [])
            risk_score = branch_dict.get("risk_score")
            score_reasons = branch_dict.get("score_reasons", [])
            branch_type = branch_dict.get("branch_type")

            path_id = f"branch_{branch_id}"
            condition = " AND ".join(active_conditions) if active_conditions else None

            branches.append(
                ExpandedBranch(
                    path_id=path_id,
                    condition=condition,
                    expanded_sql=sql,
                    is_valid=BranchValidator.validate_sql(sql),
                    risk_flags=risk_flags,
                    active_conditions=active_conditions,
                    risk_score=risk_score,
                    score_reasons=score_reasons,
                    branch_type=branch_type,
                )
            )

        return branches

    @staticmethod
    def _strip_xml_tags(sql: str) -> str:
        """Strip XML/MyBatis tags from SQL string.

        Args:
            sql: SQL string potentially containing XML tags.

        Returns:
            Clean SQL with all XML tags removed.
        """
        result = re.sub(r"<[^>]+>", "", sql)
        result = re.sub(r"\s+", " ", result)
        return result.strip()
