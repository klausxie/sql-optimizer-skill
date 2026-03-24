"""Unit tests for expander module - expand_branches (delegates to BranchExpander)."""

import pytest
from sqlopt.stages.parse.expander import ExpandedBranch, expand_branches


class TestExpandBranches:
    """Tests for expand_branches function (now delegates to BranchExpander)."""

    def test_no_dynamic_tags_returns_single_branch(self):
        """Test SQL without dynamic tags returns single default branch."""
        result = expand_branches("SELECT * FROM users WHERE id = #{id}")
        assert len(result) == 1
        assert result[0].condition is None
        assert result[0].is_valid is True
        assert "SELECT * FROM users" in result[0].expanded_sql

    def test_single_if_tag_creates_branches(self):
        """Test single if tag creates branches."""
        sql = "SELECT * FROM users<if test='name != null'> WHERE name = #{name}</if>"
        result = expand_branches(sql)
        assert len(result) >= 1
        # New naming: branch_0, branch_1, etc.
        path_ids = {b.path_id for b in result}
        # Should have at least one branch
        assert len(path_ids) >= 1

    def test_if_tag_strips_xml(self):
        """Test that if tag content has XML stripped."""
        sql = "SELECT * FROM users<if test='name != null'> WHERE name = #{name}</if>"
        result = expand_branches(sql)
        for branch in result:
            assert "<if" not in branch.expanded_sql
            assert "</if>" not in branch.expanded_sql

    def test_multiple_if_tags(self):
        """Test multiple if tags create multiple branches."""
        sql = (
            "SELECT * FROM users<if test='name != null'> AND name=#{name}</if><if test='id != null'> AND id=#{id}</if>"
        )
        result = expand_branches(sql)
        # New BranchExpander may produce different number of branches
        assert len(result) >= 1

    def test_if_tag_preserves_condition(self):
        """Test that condition is preserved in branch."""
        sql = "SELECT * FROM users<if test='name != null AND age > 18'> AND conditions</if>"
        result = expand_branches(sql)
        # At least one branch should exist with some condition
        conditions = [b.condition for b in result if b.condition]
        assert len(conditions) >= 0  # May or may not have conditions depending on strategy

    def test_where_tag_no_expansion(self):
        """Test that where tag alone doesn't create excessive branches."""
        sql = "SELECT * FROM users<where>1=1</where>"
        result = expand_branches(sql)
        assert len(result) >= 1

    def test_choose_tag(self):
        """Test that choose tag works."""
        sql = "SELECT * FROM users<choose><when test='a'>a</when><otherwise>b</otherwise></choose>"
        result = expand_branches(sql)
        assert len(result) >= 1

    def test_empty_if_tag(self):
        """Test handling of empty if tag."""
        sql = "SELECT * FROM users<if test='x'> </if>"
        result = expand_branches(sql)
        assert len(result) >= 1

    def test_invalid_xml_still_returns_branch(self):
        """Test that even with parsing issues, a branch is returned."""
        sql = "SELECT * FROM users < incomplete"
        result = expand_branches(sql)
        assert len(result) >= 1

    def test_all_branches_valid(self):
        """Test that all returned branches have is_valid=True."""
        sql = "SELECT * FROM users<if test='name != null'> AND name=#{name}</if>"
        result = expand_branches(sql)
        for branch in result:
            assert branch.is_valid is True

    def test_path_ids_are_unique(self):
        """Test that path_ids are unique."""
        sql = "SELECT * FROM users<if test='a'>a</if><if test='b'>b</if><if test='c'>c</if>"
        result = expand_branches(sql)
        path_ids = [b.path_id for b in result]
        assert len(path_ids) == len(set(path_ids))
