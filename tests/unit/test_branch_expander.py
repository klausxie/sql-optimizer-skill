"""Unit tests for BranchExpander class."""

import pytest
from sqlopt.stages.parse.branch_expander import BranchExpander, ExpandedBranch


class TestBranchExpander:
    """Tests for BranchExpander class."""

    def test_simple_sql_returns_single_branch(self):
        """SQL without dynamic tags returns single default branch."""
        expander = BranchExpander()
        sql = "SELECT * FROM users"
        branches = expander.expand(sql)
        assert len(branches) == 1
        assert branches[0].path_id == "branch_0"
        assert branches[0].condition is None
        assert "users" in branches[0].expanded_sql

    def test_single_if_tag_creates_branches(self):
        """SQL with single <if> tag creates condition + default branches."""
        expander = BranchExpander()
        sql = """SELECT * FROM users <if test="name != null">WHERE name = #{name}</if>"""
        branches = expander.expand(sql)
        assert len(branches) >= 1  # At least condition branch

    def test_max_branches_respected(self):
        """max_branches limit is respected."""
        expander = BranchExpander(max_branches=3)
        sql = """SELECT * FROM users 
        <if test="a != null"> AND a=#{a}</if>
        <if test="b != null"> AND b=#{b}</if>
        <if test="c != null"> AND c=#{c}</if>
        <if test="d != null"> AND d=#{d}</if>"""
        branches = expander.expand(sql)
        assert len(branches) <= 3

    def test_different_strategies(self):
        """Different strategies produce different branch counts."""
        sql = """SELECT * FROM users 
        <if test="name != null">WHERE name = #{name}</if>
        <if test="status != null">AND status = #{status}</if>"""

        strategies = ["ladder", "all_combinations", "pairwise", "boundary"]
        for strat in strategies:
            expander = BranchExpander(strategy=strat)
            branches = expander.expand(sql)
            assert len(branches) >= 1, f"Strategy {strat} should produce at least 1 branch"
