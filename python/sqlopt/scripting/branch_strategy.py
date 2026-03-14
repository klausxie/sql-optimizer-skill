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
    from sqlopt.scripting.sql_node import IfSqlNode


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
        pass


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

    Only generates combinations where each pair of conditions appears
    together at least once. This provides good coverage with fewer branches
    than all_combinations.

    Example for 3 conditions [c1, c2, c3]:
    - Each condition individually: [c1], [c2], [c3]
    - Each pair together: [c1, c2], [c1, c3], [c2, c3]
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

        # Helper to add unique combination
        def add_combo(combo: List[str]) -> None:
            key = tuple(sorted(combo))
            if key not in seen and len(combinations) < max_branches:
                seen.add(key)
                combinations.append(combo)

        # Add all false case
        add_combo([])

        # Add all true case
        if n <= max_branches:
            add_combo(conditions.copy())

        # Add each condition individually
        for cond in conditions:
            add_combo([cond])

        # Add pairwise combinations
        for i in range(n):
            for j in range(i + 1, n):
                if len(combinations) >= max_branches:
                    break
                add_combo([conditions[i], conditions[j]])

        # If we have room, add some triples
        if n >= 3:
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        if len(combinations) >= max_branches:
                            break
                        add_combo([conditions[i], conditions[j], conditions[k]])
                    if len(combinations) >= max_branches:
                        break

        return combinations[:max_branches]


class BoundaryStrategy(BranchGenerationStrategy):
    """Generate boundary test cases for conditions.

    Generates a small set of boundary test cases:
    - All conditions false
    - All conditions true
    - First condition true only
    - Last condition true only
    - Alternating pattern (true, false, true, ...)

    This is useful for quick validation without exhaustive testing.
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

        # 1. All false
        add_combo([])

        # 2. All true
        add_combo(conditions.copy())

        # 3. First condition true only
        if n >= 1:
            add_combo([conditions[0]])

        # 4. Last condition true only
        if n >= 2:
            add_combo([conditions[-1]])

        # 5. Alternating pattern (true, false, true, ...)
        if n >= 3:
            alt_combo = [conditions[i] for i in range(n) if i % 2 == 0]
            add_combo(alt_combo)

        # 6. Reverse alternating (false, true, false, ...)
        if n >= 3:
            alt_combo = [conditions[i] for i in range(n) if i % 2 == 1]
            add_combo(alt_combo)

        # 7. First two true
        if n >= 2:
            add_combo(conditions[:2])

        # 8. Last two true
        if n >= 2:
            add_combo(conditions[-2:])

        # 9. Middle condition true (for odd n)
        if n >= 3:
            mid = n // 2
            add_combo([conditions[mid]])

        # 10. Quarter points
        for q in [1, 3]:
            idx = (n * q) // 4
            if 0 < idx < n:
                add_combo([conditions[idx]])

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
