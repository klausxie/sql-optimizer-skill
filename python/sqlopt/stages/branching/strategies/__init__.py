"""Branch generation strategies for MyBatis XML dynamic SQL.

This module provides various strategies for generating test branches
from MyBatis conditional SQL nodes (if, choose, etc.).

Strategies:
- AllCombinationsStrategy: Generate all 2^n combinations (for n conditions)
- PairwiseStrategy: Generate pairwise combinations (reduces branch count)
- BoundaryStrategy: Generate boundary test cases (all false, all true, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from sqlopt.stages.branching.sql_node import IfSqlNode


class BranchGenerationStrategy(ABC):
    """Abstract base class for branch generation strategies.

    Each strategy defines how to generate different combinations of
    conditional branches from MyBatis dynamic SQL nodes.
    """

    @abstractmethod
    def generate(
        self, conditions: List[str], max_branches: int = 100
    ) -> List[List[str]]:
        """Generate branch combinations from a list of conditions.

        Args:
            conditions: List of OGNL test expressions from if/when nodes.
            max_branches: Maximum number of branches to generate.

        Returns:
            List of condition combinations. Each combination is a list of
            condition strings that should be evaluated as TRUE.
        """


class AllCombinationsStrategy(BranchGenerationStrategy):
    """Generate all possible 2^n combinations of conditions.

    For n conditions, generates all possible true/false combinations.
    Example for 2 conditions: [[c1], [c2], [c1, c2], []]

    This provides 100% coverage but can grow exponentially.
    """

    def generate(
        self, conditions: List[str], max_branches: int = 100
    ) -> List[List[str]]:
        """Generate all 2^n combinations.

        Args:
            conditions: List of condition strings.
            max_branches: Maximum branches to generate.

        Returns:
            List of combinations, each containing conditions to activate.
        """
        if not conditions:
            return [[]]

        n = len(conditions)
        max_possible = 2**n

        # If we can generate all combinations within limit
        if max_possible <= max_branches:
            combinations = []
            for mask in range(max_possible):
                combo = []
                for i in range(n):
                    if mask & (1 << i):
                        combo.append(conditions[i])
                combinations.append(combo)
            return combinations

        # Otherwise, generate subset (prioritize edge cases)
        combinations = []

        # Always include: all false, all true
        combinations.append([])  # All false
        combinations.append(conditions.copy())  # All true

        # Add individual conditions
        for i, cond in enumerate(conditions):
            if len(combinations) >= max_branches:
                break
            combinations.append([cond])

        # Fill remaining with random combinations
        for mask in range(max_possible):
            if len(combinations) >= max_branches:
                break
            combo = []
            for i in range(n):
                if mask & (1 << i):
                    combo.append(conditions[i])
            if combo not in combinations:
                combinations.append(combo)

        return combinations[:max_branches]


class PairwiseStrategy(BranchGenerationStrategy):
    """Generate pairwise combinations of conditions.

    Generates combinations where each condition is tested individually.
    For n conditions, generates n branches (one per condition).

    Example for 2 conditions [c1, c2]:
    - Each condition individually: [c1], [c2]
    Total: 2 branches
    """

    def generate(
        self, conditions: List[str], max_branches: int = 100
    ) -> List[List[str]]:
        """Generate pairwise combinations.

        Args:
            conditions: List of condition strings.
            max_branches: Maximum branches to generate.

        Returns:
            List of pairwise combinations.
        """
        if not conditions:
            return [[]]

        n = len(conditions)
        combinations: List[List[str]] = []
        seen = set()

        def add_combo(combo: List[str]) -> None:
            key = tuple(sorted(combo))
            if key not in seen and len(combinations) < max_branches:
                seen.add(key)
                combinations.append(combo)

        for cond in conditions:
            if len(combinations) >= max_branches:
                break
            add_combo([cond])

        return combinations[:max_branches]


class BoundaryStrategy(BranchGenerationStrategy):
    """Generate boundary test cases for conditions.

    Generates minimal boundary test cases:
    - All conditions false
    - All conditions true

    This provides basic boundary coverage with minimal branches.
    For n conditions: exactly 2 branches.
    """

    def generate(
        self, conditions: List[str], max_branches: int = 100
    ) -> List[List[str]]:
        """Generate boundary test cases.

        Args:
            conditions: List of condition strings.
            max_branches: Maximum branches to generate.

        Returns:
            List of boundary combinations.
        """
        if not conditions:
            return [[]]

        n = len(conditions)
        combinations: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()

        def add_combo(combo: List[str]) -> None:
            key = tuple(combo)
            if key not in seen and len(combinations) < max_branches:
                seen.add(key)
                combinations.append(combo)

        add_combo([])
        add_combo(conditions.copy())

        return combinations[:max_branches]


def create_strategy(
    strategy_name: str, seed: int | None = None
) -> BranchGenerationStrategy:
    """Factory function to create a branch generation strategy.

    Args:
        strategy_name: Name of the strategy.
            Options: "all_combinations", "pairwise", "boundary"
        seed: Random seed for reproducibility (not used currently).

    Returns:
        BranchGenerationStrategy instance.

    Raises:
        ValueError: If strategy_name is unknown.
    """
    strategies = {
        "all_combinations": AllCombinationsStrategy,
        "pairwise": PairwiseStrategy,
        "boundary": BoundaryStrategy,
    }

    if strategy_name not in strategies:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}"
        )

    strategy_class = strategies[strategy_name]
    return strategy_class()
