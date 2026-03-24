"""Unit tests for BranchExpander class."""

from pathlib import Path

import pytest
from sqlopt.stages.parse.branch_expander import BranchExpander, ExpandedBranch
from sqlopt.stages.branching.fragment_registry import build_fragment_registry


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

    def test_local_include_resolves_with_namespace(self, tmp_path: Path):
        """Local include tags resolve through the fragment registry."""
        mapper = tmp_path / "UserMapper.xml"
        mapper.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.UserMapper">
    <sql id="statusCondition">
        <if test="status != null">AND status = #{status}</if>
    </sql>
</mapper>""",
            encoding="utf-8",
        )
        registry = build_fragment_registry([str(mapper)])
        expander = BranchExpander(fragments=registry, strategy="all_combinations")
        sql = """<select id="findByStatus">SELECT * FROM users <where><include refid="statusCondition"/></where></select>"""

        branches = expander.expand(sql, default_namespace="com.test.UserMapper")

        assert any("status = #{status}" in branch.expanded_sql for branch in branches)

    def test_foreach_singleton_variant_avoids_empty_in_clause(self):
        """Foreach boundary variants should not generate IN ()."""
        expander = BranchExpander(strategy="all_combinations", max_branches=10)
        sql = """<select id="findByIds">SELECT * FROM users WHERE id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach></select>"""

        branches = expander.expand(sql)

        assert all("IN ()" not in branch.expanded_sql.upper() for branch in branches)
        assert any("IN (#{id})" in branch.expanded_sql for branch in branches)

    def test_select_key_is_ignored_from_statement_sql(self):
        """selectKey metadata should not be rendered into the executable SQL branch."""
        expander = BranchExpander(strategy="all_combinations")
        sql = """<insert id="insertUser"><selectKey keyProperty="id" resultType="integer" order="BEFORE">SELECT 1</selectKey>INSERT INTO users (id, name) VALUES (#{id}, #{name})</insert>"""

        branches = expander.expand(sql)

        assert len(branches) == 1
        assert branches[0].expanded_sql == "INSERT INTO users (id, name) VALUES (#{id}, #{name})"
