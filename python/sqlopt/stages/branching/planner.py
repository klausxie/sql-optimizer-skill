from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from sqlopt.common.defaults import DEFAULT_MAX_BRANCHES
from sqlopt.stages.branching.dimension_extractor import BranchDimension

# Trigger complement sweep when conditions > this threshold
COMPLEMENT_TRIGGER_THRESHOLD = 10
# Max complement combinations to generate
COMPLEMENT_MAX_COMBINATIONS = 10
# Min/Max combination widths for complement sweep
COMPLEMENT_MIN_WIDTH = 5
COMPLEMENT_MAX_WIDTH = 6


@dataclass
class DimensionCandidate:
    dimension: BranchDimension
    score: float


class RiskGuidedLadderPlanner:
    """Budget-aware planner for ladder strategy without full enumeration."""

    def __init__(self, max_branches: int = DEFAULT_MAX_BRANCHES) -> None:
        self.max_branches = max_branches

    def generate(
        self,
        candidates: list[DimensionCandidate],
    ) -> list[list[str]]:
        if not candidates:
            return [[]]

        combinations_out: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()

        def add_combo(conditions: tuple[str, ...]) -> bool:
            normalized = self._normalize_conditions(conditions)
            key = tuple(normalized)
            if not normalized or key not in seen:
                if len(combinations_out) >= self.max_branches:
                    return False
                seen.add(key)
                combinations_out.append(normalized)
                return True
            return False

        sorted_candidates = sorted(
            candidates,
            key=lambda candidate: (
                candidate.score,
                -candidate.dimension.depth,
                candidate.dimension.condition,
            ),
            reverse=True,
        )

        add_combo(())

        for candidate in sorted_candidates:
            if len(combinations_out) >= self.max_branches:
                break
            add_combo(candidate.dimension.activation_conditions)

        for combo in self._generate_complement_sweep(sorted_candidates):
            if len(combinations_out) >= self.max_branches:
                break
            add_combo(tuple(combo))

        top_pair_candidates = sorted_candidates[: min(12, len(sorted_candidates))]
        for pair in combinations(top_pair_candidates, 2):
            if len(combinations_out) >= self.max_branches:
                break
            if self._has_mutex_conflict(pair):
                continue
            add_combo(self._merge_candidate_conditions(pair))

        top_triple_candidates = sorted_candidates[: min(8, len(sorted_candidates))]
        for triple in combinations(top_triple_candidates, 3):
            if len(combinations_out) >= self.max_branches:
                break
            if self._has_mutex_conflict(triple):
                continue
            add_combo(self._merge_candidate_conditions(triple))

        for width in range(4, min(5, len(top_triple_candidates) + 1)):
            for subset in combinations(top_triple_candidates, width):
                if len(combinations_out) >= self.max_branches:
                    break
                if self._has_mutex_conflict(subset):
                    continue
                add_combo(self._merge_candidate_conditions(subset))

        return combinations_out[: self.max_branches]

    @staticmethod
    def _merge_candidate_conditions(
        candidates: tuple[DimensionCandidate, ...],
    ) -> tuple[str, ...]:
        merged: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            for condition in candidate.dimension.activation_conditions:
                if condition and condition not in seen:
                    seen.add(condition)
                    merged.append(condition)
        return tuple(merged)

    @staticmethod
    def _has_mutex_conflict(
        candidates: tuple[DimensionCandidate, ...],
    ) -> bool:
        seen_groups: set[str] = set()
        for candidate in candidates:
            group = candidate.dimension.mutex_group
            if not group:
                continue
            if group in seen_groups:
                return True
            seen_groups.add(group)
        return False

    @staticmethod
    def _normalize_conditions(conditions: tuple[str, ...]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for condition in conditions:
            if condition and condition not in seen:
                seen.add(condition)
                normalized.append(condition)
        return normalized

    def _generate_complement_sweep(
        self,
        candidates: list[DimensionCandidate],
        budget: int = COMPLEMENT_MAX_COMBINATIONS,
    ) -> list[list[str]]:
        if len(candidates) <= COMPLEMENT_TRIGGER_THRESHOLD:
            return []

        top_12 = candidates[: min(12, len(candidates))]
        top_12_ids = {id(c) for c in top_12}
        middle_risk = [c for c in candidates if id(c) not in top_12_ids]

        if not middle_risk:
            return []

        middle_risk_ids = {id(c) for c in middle_risk}

        combos: list[tuple[DimensionCandidate, ...]] = []

        for width in range(COMPLEMENT_MIN_WIDTH, COMPLEMENT_MAX_WIDTH + 1):
            if width > len(candidates):
                continue
            for combo in combinations(candidates, width):
                if not any(id(c) in middle_risk_ids for c in combo):
                    continue
                if self._has_mutex_conflict(combo):
                    continue
                combos.append(combo)

        combos.sort(key=lambda c: sum(x.score for x in c), reverse=True)

        results: list[list[str]] = []
        for combo in combos[:budget]:
            merged = self._merge_candidate_conditions(combo)
            results.append(merged)

        return results
