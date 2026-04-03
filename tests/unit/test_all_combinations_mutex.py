"""Tests for AllCombinationsStrategy mutex filtering (ChooseSqlNode)."""

from __future__ import annotations

from sqlopt.stages.branching.branch_strategy import (
    AllCombinationsStrategy,
    _has_choose_mutex_conflict,
)


class TestHasChooseMutexConflict:
    """Tests for the _has_choose_mutex_conflict helper."""

    def test_no_conflict_empty(self) -> None:
        assert not _has_choose_mutex_conflict([], {"c1": "choose_1"})

    def test_no_conflict_single(self) -> None:
        assert not _has_choose_mutex_conflict(["c1"], {"c1": "choose_1"})

    def test_conflict_same_group(self) -> None:
        assert _has_choose_mutex_conflict(
            ["c1", "c2"],
            {"c1": "choose_1", "c2": "choose_1"},
        )

    def test_no_conflict_different_groups(self) -> None:
        assert not _has_choose_mutex_conflict(
            ["c1", "c2"],
            {"c1": "choose_1", "c2": "choose_2"},
        )

    def test_no_conflict_mixed(self) -> None:
        assert not _has_choose_mutex_conflict(
            ["c1", "c3"],
            {"c1": "choose_1", "c2": "choose_1"},
        )

    def test_conflict_with_non_mutex_condition(self) -> None:
        assert _has_choose_mutex_conflict(
            ["c1", "c2", "c3"],
            {"c1": "choose_1", "c2": "choose_1"},
        )


class TestAllCombinationsMutexFiltering:
    """Tests for AllCombinationsStrategy.generate() with mutex_groups."""

    def setup_method(self) -> None:
        self.strategy = AllCombinationsStrategy()

    def test_same_choose_filters_combined(self) -> None:
        result = self.strategy.generate(
            ["c1", "c2"],
            mutex_groups={"c1": "choose_1", "c2": "choose_1"},
        )
        assert ["c1", "c2"] not in result
        assert [] in result
        assert ["c1"] in result
        assert ["c2"] in result

    def test_different_choose_all_allowed(self) -> None:
        result = self.strategy.generate(
            ["c1", "c2"],
            mutex_groups={"c1": "choose_1", "c2": "choose_2"},
        )
        assert len(result) == 4

    def test_none_mutex_groups_backward_compatible(self) -> None:
        result = self.strategy.generate(["a", "b"], mutex_groups=None)
        assert len(result) == 4

    def test_no_mutex_groups_backward_compatible(self) -> None:
        result = self.strategy.generate(["a", "b"])
        assert len(result) == 4

    def test_three_choose_branches(self) -> None:
        result = self.strategy.generate(
            ["w1", "w2", "w3"],
            mutex_groups={"w1": "ch1", "w2": "ch1", "w3": "ch1"},
        )
        for combo in result:
            choose_count = sum(1 for c in combo if c in ("w1", "w2", "w3"))
            assert choose_count <= 1, f"Combo {combo} has {choose_count} choose conditions"

    def test_mixed_mutex_and_free_conditions(self) -> None:
        result = self.strategy.generate(
            ["w1", "w2", "if1"],
            mutex_groups={"w1": "ch1", "w2": "ch1"},
        )
        for combo in result:
            has_w1 = "w1" in combo
            has_w2 = "w2" in combo
            assert not (has_w1 and has_w2), f"Combo {combo} has both w1 and w2"

    def test_subset_path_with_mutex(self) -> None:
        result = self.strategy.generate(
            ["w1", "w2"],
            max_branches=2,
            mutex_groups={"w1": "ch1", "w2": "ch1"},
        )
        for combo in result:
            has_w1 = "w1" in combo
            has_w2 = "w2" in combo
            assert not (has_w1 and has_w2), f"Combo {combo} has both w1 and w2"

    def test_empty_conditions_with_mutex(self) -> None:
        result = self.strategy.generate(
            [],
            mutex_groups={"c1": "ch1"},
        )
        assert result == [[]]
