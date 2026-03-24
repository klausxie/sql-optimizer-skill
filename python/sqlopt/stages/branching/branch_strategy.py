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
    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
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

    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
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

    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
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

    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
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


class LadderSamplingStrategy(BranchGenerationStrategy):
    """Ladder sampling with risk weighting and metadata enhancement.

    This strategy combines:
    1. Single-factor coverage (every condition T/F)
    2. High-weight pairwise coverage (top-K pairs)
    3. High-weight triple coverage (top-K triples)
    4. Greedy fill by risk score

    Coverage estimation (based on 100 slow SQL assumption):
    - 60% single-factor issues -> 100% covered
    - 25% pairwise issues -> ~40% covered (top pairs)
    - 10% triple issues -> ~15% covered (top triples)

    Example for 15 conditions targeting 50 branches:
    - Step1: 16 branches (15 single + all false)
    - Step2: ~20 branches (top pairwise)
    - Step3: ~5 branches (top triples)
    - Step4: ~9 branches (greedy fill)
    - Total: ~50 branches with ~62% recall
    """

    # Default risk weights based on SQL text features
    DEFAULT_WEIGHTS = {
        "large_table": 3,  # Involves large table (users/orders/logs)
        "join": 2,  # JOIN is expensive
        "select_star": 2,  # SELECT * causes extra columns
        "subquery": 2,  # Subquery amplifies data
        "like_prefix": 2,  # LIKE '%xxx' can't use index
        "or_condition": 1,  # OR is hard to index
        "order_by": 1,  # Sorting cost
        "group_by": 1,  # Grouping cost
    }

    def __init__(
        self,
        condition_weights: dict[str, float] | None = None,
        table_metadata: dict[str, dict] | None = None,
    ) -> None:
        """Initialize ladder strategy.

        Args:
            condition_weights: Dict mapping condition -> risk weight (0-10).
                Higher = more risky. If not provided, use default weights.
            table_metadata: Dict mapping table_name -> metadata dict with:
                - size: "large" | "medium" | "small"
                - indexes: list of indexed columns
        """
        self.condition_weights = condition_weights or {}
        self.table_metadata = table_metadata or {}

    def generate(self, conditions: List[str], max_branches: int = 100) -> List[List[str]]:
        """Generate ladder-sampled combinations.

        Args:
            conditions: List of condition strings.
            max_branches: Maximum branches to generate.

        Returns:
            List of combinations following ladder sampling.
        """
        if not conditions:
            return [[]]

        n = len(conditions)
        combinations: List[List[str]] = []
        seen: set[tuple[str, ...]] = set()

        def add_combo(combo: List[str]) -> bool:
            """Add combo if not duplicate. Returns True if added."""
            key = tuple(sorted(combo))
            if key not in seen and len(combinations) < max_branches:
                seen.add(key)
                combinations.append(combo)
                return True
            return False

        # === Step 1: Single-factor coverage ===
        # All false (baseline)
        add_combo([])

        # Each condition true
        for i, cond in enumerate(conditions):
            add_combo([cond])

        # === Step 2: High-weight pairwise coverage ===
        # Calculate pairwise weights
        pairwise_weights: dict[tuple[int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                w_i = self._get_condition_weight(conditions[i])
                w_j = self._get_condition_weight(conditions[j])
                pairwise_weights[(i, j)] = w_i + w_j

        # Sort pairs by weight descending
        sorted_pairs = sorted(pairwise_weights.keys(), key=lambda p: pairwise_weights[p], reverse=True)

        # Add top pairwise combinations (both T,T and T,F for each)
        top_k_pairs = min(10, len(sorted_pairs))
        for idx in range(top_k_pairs):
            i, j = sorted_pairs[idx]
            # T,T combination
            add_combo([conditions[i], conditions[j]])

        # === Step 3: High-weight triple coverage ===
        triple_weights: dict[tuple[int, int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    w_i = self._get_condition_weight(conditions[i])
                    w_j = self._get_condition_weight(conditions[j])
                    w_k = self._get_condition_weight(conditions[k])
                    triple_weights[(i, j, k)] = w_i + w_j + w_k

        # Add top triples
        sorted_triples = sorted(triple_weights.keys(), key=lambda t: triple_weights[t], reverse=True)

        top_k_triples = min(5, len(sorted_triples))
        for idx in range(top_k_triples):
            i, j, k = sorted_triples[idx]
            add_combo([conditions[i], conditions[j], conditions[k]])

        # === Step 4: Greedy fill by total risk score ===
        # Calculate total weight for each condition
        cond_weights = [(i, self._get_condition_weight(conditions[i])) for i in range(n)]
        cond_weights.sort(key=lambda x: x[1], reverse=True)

        # Greedy: pick combinations with highest total weight
        while len(combinations) < max_branches:
            # Find highest weight combo not yet added
            best_combo = None
            best_score = -1

            for mask in range(1, 2**n):
                combo = []
                for i in range(n):
                    if mask & (1 << i):
                        combo.append(conditions[i])
                if tuple(sorted(combo)) in seen:
                    continue
                score = sum(self._get_condition_weight(c) for c in combo)
                if score > best_score:
                    best_score = score
                    best_combo = combo

            if best_combo is None or not add_combo(best_combo):
                break

        return combinations[:max_branches]

    def _get_condition_weight(self, condition: str) -> float:
        """Get risk weight for a condition.

        Args:
            condition: Condition expression string.

        Returns:
            Risk weight (0-10+).
        """
        # Use provided weight if available
        if condition in self.condition_weights:
            return self.condition_weights[condition]

        # Default weight based on pattern matching
        weight = 1.0  # Base weight

        condition_lower = condition.lower()

        # Check for high-risk patterns
        if any(kw in condition_lower for kw in ["users", "orders", "logs"]):
            weight += 3  # Large table
        if "join" in condition_lower:
            weight += 2
        if "select" in condition_lower and "*" in condition_lower:
            weight += 2
        if "subquery" in condition_lower or "in (" in condition_lower:
            weight += 2
        if "%" in condition:  # LIKE with wildcard
            weight += 2
        if " or " in condition_lower:
            weight += 1
        if "order by" in condition_lower:
            weight += 1
        if "group by" in condition_lower:
            weight += 1

        return weight


def create_strategy(strategy_name: str, seed: int | None = None) -> BranchGenerationStrategy:
    """Factory function to create a branch generation strategy.

    Args:
        strategy_name: Name of the strategy.
            Options: "all_combinations", "pairwise", "boundary", "ladder"
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
        "ladder": LadderSamplingStrategy,
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}")

    strategy_class = strategies[strategy_name]
    return strategy_class()
