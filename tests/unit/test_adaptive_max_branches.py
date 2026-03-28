"""Unit tests for adaptive_max_branches formula.

Formula: min(max(BASE, 2**(n-1)), CAP) for 2**n > BASE
"""

from __future__ import annotations

import pytest

from sqlopt.stages.parse.branch_expander import adaptive_max_branches


class TestAdaptiveMaxBranches:
    """Tests for adaptive_max_branches function."""

    def test_zero_conditions_returns_one_all_combinations(self):
        cap, strategy = adaptive_max_branches(0)
        assert cap == 1
        assert strategy == "all_combinations"

    def test_negative_returns_one_all_combinations(self):
        cap, strategy = adaptive_max_branches(-5)
        assert cap == 1
        assert strategy == "all_combinations"

    def test_n1_full_enumeration(self):
        cap, strategy = adaptive_max_branches(1, base=50, cap=1000)
        assert cap == 2
        assert strategy == "all_combinations"

    def test_n2_full_enumeration(self):
        cap, strategy = adaptive_max_branches(2, base=50, cap=1000)
        assert cap == 4
        assert strategy == "all_combinations"

    def test_n3_full_enumeration(self):
        cap, strategy = adaptive_max_branches(3, base=50, cap=1000)
        assert cap == 8
        assert strategy == "all_combinations"

    def test_n4_full_enumeration(self):
        cap, strategy = adaptive_max_branches(4, base=50, cap=1000)
        assert cap == 16
        assert strategy == "all_combinations"

    def test_n5_full_enumeration(self):
        cap, strategy = adaptive_max_branches(5, base=50, cap=1000)
        assert cap == 32
        assert strategy == "all_combinations"

    def test_n6_switches_to_ladder(self):
        cap, strategy = adaptive_max_branches(6, base=50, cap=1000)
        assert strategy == "ladder"
        assert cap == 50

    def test_n7_ladder_cap(self):
        cap, strategy = adaptive_max_branches(7, base=50, cap=1000)
        assert strategy == "ladder"
        assert cap == 64

    def test_cap_hard_limit(self):
        cap, strategy = adaptive_max_branches(100, base=50, cap=500)
        assert cap == 500

    def test_base_override_lowers_switching_threshold(self):
        cap, strategy = adaptive_max_branches(4, base=10, cap=1000)
        assert strategy == "ladder"
        assert cap == 10

    def test_base_override_at_boundary(self):
        cap, strategy = adaptive_max_branches(6, base=64, cap=1000)
        assert strategy == "all_combinations"
        assert cap == 64


class TestAdaptiveMonotonicity:
    """Monotonicity: output should never decrease as n increases."""

    def test_monotonic_n_1_to_10(self):
        prev = 0
        for n in range(1, 11):
            cap, _ = adaptive_max_branches(n, base=50, cap=1000)
            assert cap >= prev, f"Non-monotonic at n={n}: {cap} < {prev}"
            prev = cap

    def test_monotonic_n_1_to_15(self):
        prev = 0
        for n in range(1, 16):
            cap, _ = adaptive_max_branches(n, base=50, cap=1000)
            assert cap >= prev, f"Non-monotonic at n={n}: {cap} < {prev}"
            prev = cap

    def test_monotonic_n_1_to_20(self):
        prev = 0
        for n in range(1, 21):
            cap, _ = adaptive_max_branches(n, base=50, cap=1000)
            assert cap >= prev, f"Non-monotonic at n={n}: {cap} < {prev}"
            prev = cap


class TestAdaptiveEdgeCases:
    """Edge case handling."""

    def test_cap_equals_base(self):
        cap, strategy = adaptive_max_branches(6, base=50, cap=50)
        assert cap == 50
        assert strategy == "ladder"

    def test_cap_less_than_base(self):
        cap, strategy = adaptive_max_branches(6, base=50, cap=10)
        assert cap == 10
        assert strategy == "ladder"

    def test_base_one_uses_ladder(self):
        cap, strategy = adaptive_max_branches(3, base=1, cap=1000)
        assert cap == 4
        assert strategy == "ladder"

    def test_cap_one(self):
        cap, strategy = adaptive_max_branches(10, base=50, cap=1)
        assert cap == 1
