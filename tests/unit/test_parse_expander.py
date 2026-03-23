"""Unit tests for expander module - expand_branches, _strip_xml_tags."""

import pytest
from sqlopt.stages.parse.expander import ExpandedBranch, _strip_xml_tags, expand_branches


class TestStripXmlTags:
    """Tests for _strip_xml_tags function."""

    def test_strip_simple_tags(self):
        """Test stripping simple XML tags."""
        result = _strip_xml_tags("<select>SELECT * FROM users</select>")
        assert result == "SELECT * FROM users"

    def test_strip_if_tag(self):
        """Test stripping if tag."""
        result = _strip_xml_tags("<if test='name != null'>AND name = 'test'</if>")
        assert result == "AND name = 'test'"

    def test_strip_multiple_tags(self):
        """Test stripping multiple tags."""
        result = _strip_xml_tags("<if>a</if><where>b</where><set>c</set>")
        assert result == "abc"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        result = _strip_xml_tags("<a>  hello   world  </a>")
        assert result == "hello world"

    def test_empty_input(self):
        """Test empty input."""
        result = _strip_xml_tags("")
        assert result == ""

    def test_no_tags_unchanged(self):
        """Test text without tags is unchanged."""
        result = _strip_xml_tags("SELECT * FROM users WHERE id = 1")
        assert result == "SELECT * FROM users WHERE id = 1"


class TestExpandBranches:
    """Tests for expand_branches function."""

    def test_no_dynamic_tags_returns_single_branch(self):
        """Test SQL without dynamic tags returns single default branch."""
        result = expand_branches("SELECT * FROM users WHERE id = #{id}")
        assert len(result) == 1
        assert result[0].path_id == "default"
        assert result[0].condition is None
        assert result[0].is_valid is True
        assert "SELECT * FROM users" in result[0].expanded_sql

    def test_single_if_tag_creates_two_branches(self):
        """Test single if tag creates branch for condition and default."""
        sql = "SELECT * FROM users<if test='name != null'> WHERE name = #{name}</if>"
        result = expand_branches(sql)
        assert len(result) == 2
        assert result[0].path_id == "if_0"
        assert result[0].condition == "name != null"
        assert result[1].path_id == "default"

    def test_if_tag_strips_xml(self):
        """Test that if tag content has XML stripped."""
        sql = "SELECT * FROM users<if test='name != null'> WHERE name = #{name}</if>"
        result = expand_branches(sql)
        if_branch = next(b for b in result if b.path_id == "if_0")
        assert "<if" not in if_branch.expanded_sql
        assert "</if>" not in if_branch.expanded_sql

    def test_multiple_if_tags(self):
        """Test multiple if tags create multiple branches."""
        sql = "SELECT * FROM users<if test='name != null'> AND name=#{name}</if><if test='id != null'> AND id=#{id}</if>"
        result = expand_branches(sql)
        assert len(result) == 3
        path_ids = {b.path_id for b in result}
        assert path_ids == {"if_0", "if_1", "default"}

    def test_if_tag_preserves_condition(self):
        """Test that condition is preserved in branch."""
        sql = "SELECT * FROM users<if test='name != null AND age > 18'> AND conditions</if>"
        result = expand_branches(sql)
        if_branch = next(b for b in result if b.path_id == "if_0")
        assert if_branch.condition == "name != null AND age > 18"

    def test_where_tag_no_expansion(self):
        """Test that where tag alone doesn't create branches."""
        sql = "SELECT * FROM users<where>1=1</where>"
        result = expand_branches(sql)
        assert len(result) == 1
        assert result[0].path_id == "default"

    def test_choose_tag_no_expansion(self):
        """Test that choose tag alone doesn't create branches."""
        sql = "SELECT * FROM users<choose><when test='a'>a</when><otherwise>b</otherwise></choose>"
        result = expand_branches(sql)
        assert len(result) == 1

    def test_empty_if_tag(self):
        """Test handling of empty if tag."""
        sql = "SELECT * FROM users<if test='x'> </if>"
        result = expand_branches(sql)
        assert len(result) == 2

    def test_nested_if_only_expands_outer(self):
        """Test that only outer if is expanded (simple parser)."""
        sql = "SELECT * FROM users<if test='a'><if test='b'>nested</if></if>"
        result = expand_branches(sql)
        assert len(result) == 2

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
