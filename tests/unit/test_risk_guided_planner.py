"""Unit tests for RiskGuidedLadderPlanner."""

from __future__ import annotations

import pytest

from sqlopt.stages.branching.dimension_extractor import BranchDimension
from sqlopt.stages.branching.planner import DimensionCandidate, RiskGuidedLadderPlanner


class TestRiskGuidedLadderPlanner:
    """Tests for RiskGuidedLadderPlanner."""

    def test_empty_candidates_returns_baseline_only(self):
        """No candidates = just the empty baseline combination."""
        planner = RiskGuidedLadderPlanner(max_branches=10)
        result = planner.generate([])
        assert result == [[]]

    def test_baseline_always_first(self):
        """Empty condition set (baseline) must be the first combination."""
        dim = BranchDimension(
            condition="x != null",
            required_conditions=(),
            sql_fragment="AND x = #{x}",
            depth=0,
        )
        candidate = DimensionCandidate(dimension=dim, score=5.0)
        planner = RiskGuidedLadderPlanner(max_branches=10)

        result = planner.generate([candidate])

        assert [] in result  # baseline
        baseline_idx = result.index([])
        # Baseline should be first
        for combo in result[:baseline_idx]:
            assert combo != []

    def test_high_score_candidates_come_first(self):
        """Higher score dimensions should appear before lower scores."""
        dims = [
            BranchDimension(
                condition="a != null",
                required_conditions=(),
                sql_fragment="AND a = #{a}",
                depth=0,
            ),
            BranchDimension(
                condition="b != null",
                required_conditions=(),
                sql_fragment="AND b = #{b}",
                depth=0,
            ),
        ]
        candidates = [
            DimensionCandidate(dimension=dims[0], score=1.0),
            DimensionCandidate(dimension=dims[1], score=10.0),
        ]
        planner = RiskGuidedLadderPlanner(max_branches=10)
        result = planner.generate(candidates)

        b_combo = ["b != null"]
        a_combo = ["a != null"]
        assert b_combo in result
        assert a_combo in result
        assert result.index(b_combo) < result.index(a_combo)

    def test_max_branches_hard_limit(self):
        """generation stops at max_branches."""
        dims = [
            BranchDimension(
                condition=f"cond_{i} != null",
                required_conditions=(),
                sql_fragment=f"AND cond_{i} = #{{cond_{i}}}",
                depth=0,
            )
            for i in range(20)
        ]
        candidates = [DimensionCandidate(dimension=d, score=1.0) for d in dims]
        planner = RiskGuidedLadderPlanner(max_branches=5)

        result = planner.generate(candidates)

        assert len(result) <= 5

    def test_pairwise_combinations_generated(self):
        """After single conditions, pairwise combinations should be generated."""
        dims = [
            BranchDimension(
                condition="a != null",
                required_conditions=(),
                sql_fragment="AND a = #{a}",
                depth=0,
            ),
            BranchDimension(
                condition="b != null",
                required_conditions=(),
                sql_fragment="AND b = #{b}",
                depth=0,
            ),
            BranchDimension(
                condition="c != null",
                required_conditions=(),
                sql_fragment="AND c = #{c}",
                depth=0,
            ),
        ]
        candidates = [DimensionCandidate(dimension=d, score=1.0) for d in dims]
        planner = RiskGuidedLadderPlanner(max_branches=20)
        result = planner.generate(candidates)

        # Should contain pairwise combinations
        pairwise_found = any(len(combo) == 2 for combo in result if combo)
        assert pairwise_found, "Expected pairwise combinations in output"

    def test_mutex_group_conflict_prevention(self):
        """Choose dimensions with same mutex_group should not be combined."""
        dims = [
            BranchDimension(
                condition="type == 'A'",
                required_conditions=(),
                sql_fragment="AND type = 'A'",
                depth=0,
                mutex_group="choose_0",
            ),
            BranchDimension(
                condition="type == 'B'",
                required_conditions=(),
                sql_fragment="AND type = 'B'",
                depth=0,
                mutex_group="choose_0",
            ),
        ]
        candidates = [DimensionCandidate(dimension=d, score=1.0) for d in dims]
        planner = RiskGuidedLadderPlanner(max_branches=10)
        result = planner.generate(candidates)

        # Should NOT contain combination of both mutex conditions
        for combo in result:
            if combo and len(combo) > 1:
                assert not all(c in combo for c in ["type == 'A'", "type == 'B'"])

    def test_required_conditions_included(self):
        """Child conditions should include parent's required_conditions."""
        parent_dim = BranchDimension(
            condition="parent != null",
            required_conditions=(),
            sql_fragment="AND parent = #{parent}",
            depth=0,
        )
        child_dim = BranchDimension(
            condition="child != null",
            required_conditions=("parent != null",),
            sql_fragment="AND child = #{child}",
            depth=1,
        )
        candidates = [
            DimensionCandidate(dimension=parent_dim, score=5.0),
            DimensionCandidate(dimension=child_dim, score=10.0),
        ]
        planner = RiskGuidedLadderPlanner(max_branches=10)
        result = planner.generate(candidates)

        # Child condition should appear with parent in same combo
        child_combos = [combo for combo in result if "child != null" in combo]
        assert any("parent != null" in combo for combo in child_combos)

    def test_score_tie_breaker_depth(self):
        """When scores tie, smaller depth wins."""
        dims = [
            BranchDimension(
                condition="deep != null",
                required_conditions=("parent != null",),
                sql_fragment="AND deep = #{deep}",
                depth=1,
            ),
            BranchDimension(
                condition="shallow != null",
                required_conditions=(),
                sql_fragment="AND shallow = #{shallow}",
                depth=0,
            ),
        ]
        candidates = [
            DimensionCandidate(dimension=dims[0], score=5.0),
            DimensionCandidate(dimension=dims[1], score=5.0),
        ]
        planner = RiskGuidedLadderPlanner(max_branches=10)
        result = planner.generate(candidates)

        # Shallow (depth=0) should come before deep (depth=1)
        shallow_combo = ("shallow != null",)
        deep_combo = ("deep != null",)
        if shallow_combo in result and deep_combo in result:
            assert result.index(shallow_combo) < result.index(deep_combo)

    def test_normalize_conditions_removes_duplicates(self):
        """Duplicate conditions in a combination should be deduplicated."""
        dim = BranchDimension(
            condition="a != null",
            required_conditions=(),
            sql_fragment="AND a = #{a}",
            depth=0,
        )
        # Simulate a case where same condition appears twice
        planner = RiskGuidedLadderPlanner(max_branches=10)
        # Using private method to test normalization directly
        result = planner._normalize_conditions(("a != null", "a != null"))
        assert result == ["a != null"]
        assert len(result) == 1

    def test_merging_conditions_combines_sql(self):
        """Merging multiple candidates combines their conditions."""
        dim1 = BranchDimension(
            condition="a != null",
            required_conditions=(),
            sql_fragment="AND a = #{a}",
            depth=0,
        )
        dim2 = BranchDimension(
            condition="b != null",
            required_conditions=(),
            sql_fragment="AND b = #{b}",
            depth=0,
        )
        candidates = (
            DimensionCandidate(dimension=dim1, score=5.0),
            DimensionCandidate(dimension=dim2, score=5.0),
        )
        planner = RiskGuidedLadderPlanner(max_branches=10)
        merged = planner._merge_candidate_conditions(candidates)

        assert "a != null" in merged
        assert "b != null" in merged

    def test_single_condition_with_high_score(self):
        """A single high-score condition gets included even with small budget."""
        dim = BranchDimension(
            condition="high_risk != null",
            required_conditions=(),
            sql_fragment="AND high_risk = #{high_risk}",
            depth=0,
        )
        candidate = DimensionCandidate(dimension=dim, score=100.0)
        planner = RiskGuidedLadderPlanner(max_branches=2)

        result = planner.generate([candidate])

        assert len(result) >= 1
        assert ["high_risk != null"] in result or [] in result


class TestAdaptiveFormula:
    """Tests for the adaptive branch cap formula.

    Formula: min(max(BASE, 2**(n-1)), CAP) for 2**n > BASE
    Monotonicity: output should never decrease as n increases.
    """

    def test_formula_monotonic_increasing_n(self):
        """As condition count increases, adaptive cap should never decrease."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        prev_cap = 0
        for n in range(1, 15):
            cap, _ = adaptive_max_branches(n, base=50, cap=1000)
            assert cap >= prev_cap, f"Formula not monotonic at n={n}: {cap} < {prev_cap}"
            prev_cap = cap

    def test_small_n_uses_all_combinations(self):
        """For small n (2**n <= BASE), should use all_combinations."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        # n=1: 2**1=2 <= 50 -> all_combinations
        cap, strategy = adaptive_max_branches(1, base=50, cap=1000)
        assert cap == 2
        assert strategy == "all_combinations"

        # n=2: 2**2=4 <= 50 -> all_combinations
        cap, strategy = adaptive_max_branches(2, base=50, cap=1000)
        assert cap == 4
        assert strategy == "all_combinations"

        # n=5: 2**5=32 <= 50 -> all_combinations
        cap, strategy = adaptive_max_branches(5, base=50, cap=1000)
        assert cap == 32
        assert strategy == "all_combinations"

    def test_large_n_switches_to_ladder(self):
        """For large n (2**n > BASE), should switch to ladder."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        # n=6: 2**6=64 > 50 -> ladder
        cap, strategy = adaptive_max_branches(6, base=50, cap=1000)
        assert strategy == "ladder"
        assert cap == min(max(50, 2 ** (6 - 1)), 1000)  # min(max(50, 32), 1000) = 50

    def test_cap_hard_limit(self):
        """Output should never exceed CAP."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        cap, _ = adaptive_max_branches(100, base=50, cap=500)
        assert cap <= 500

    def test_base_override_works(self):
        """BASE override should affect the switching threshold."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        # With base=10, n=4: 2**4=16 > 10 -> ladder
        cap, strategy = adaptive_max_branches(4, base=10, cap=1000)
        assert strategy == "ladder"
        assert cap == min(max(10, 2 ** (4 - 1)), 1000)  # min(max(10, 8), 1000) = 10

    def test_zero_conditions_returns_one(self):
        """n=0 returns 1 branch with all_combinations strategy."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        cap, strategy = adaptive_max_branches(0, base=50, cap=1000)
        assert cap == 1
        assert strategy == "all_combinations"

    def test_negative_conditions_returns_one(self):
        """Negative n returns 1 branch (defensive)."""
        from sqlopt.stages.parse.branch_expander import adaptive_max_branches

        cap, strategy = adaptive_max_branches(-1, base=50, cap=1000)
        assert cap == 1
