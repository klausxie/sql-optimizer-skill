"""Tests for _normalize_sql_whitespace function."""

import pytest

from python.sqlopt.application.v9_stages.init import _normalize_sql_whitespace


class TestNormalizeSqlWhitespace:
    """Test cases for _normalize_sql_whitespace."""

    def test_collapse_multiple_spaces(self):
        """Multiple spaces should be collapsed to single space."""
        assert (
            _normalize_sql_whitespace("SELECT  1 FROM users") == "SELECT 1 FROM users"
        )

    def test_collapse_newlines_to_space(self):
        """Newlines should be collapsed to single space."""
        assert (
            _normalize_sql_whitespace("SELECT 1\nFROM users") == "SELECT 1 FROM users"
        )

    def test_preserve_string_literal(self):
        """String literal content should be preserved exactly."""
        assert (
            _normalize_sql_whitespace("SELECT 'a  b' FROM users")
            == "SELECT 'a  b' FROM users"
        )

    def test_preserve_escaped_quote_in_string(self):
        """Escaped quotes ('') within string should be preserved."""
        assert (
            _normalize_sql_whitespace("SELECT 'it''s' FROM users")
            == "SELECT 'it''s' FROM users"
        )

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _normalize_sql_whitespace("") == ""

    def test_none_input(self):
        """None input should return empty string."""
        assert _normalize_sql_whitespace(None) == ""

    def test_mixed_spaces_and_newlines(self):
        """Mixed whitespace should be normalized."""
        input_sql = "SELECT  1\n\nFROM   users"
        expected = "SELECT 1 FROM users"
        assert _normalize_sql_whitespace(input_sql) == expected

    def test_string_with_multiple_spaces(self):
        """String containing multiple spaces should be preserved."""
        input_sql = "SELECT 'hello   world' FROM users"
        expected = "SELECT 'hello   world' FROM users"
        assert _normalize_sql_whitespace(input_sql) == expected

    def test_multiple_strings(self):
        """Multiple strings in SQL should all be preserved."""
        input_sql = "SELECT 'a'  ,  'b' FROM t"
        expected = "SELECT 'a' , 'b' FROM t"
        assert _normalize_sql_whitespace(input_sql) == expected

    def test_string_with_newlines(self):
        """String containing newlines should be preserved."""
        input_sql = "SELECT 'line1\nline2' FROM users"
        expected = "SELECT 'line1\nline2' FROM users"
        assert _normalize_sql_whitespace(input_sql) == expected

    def test_no_whitespace_change_needed(self):
        """SQL already normalized should be unchanged."""
        input_sql = "SELECT 1 FROM users WHERE id = 1"
        expected = "SELECT 1 FROM users WHERE id = 1"
        assert _normalize_sql_whitespace(input_sql) == expected

    def test_leading_trailing_whitespace(self):
        """Leading and trailing whitespace should be collapsed to single space."""
        input_sql = "  SELECT 1 FROM users  "
        expected = " SELECT 1 FROM users "
        assert _normalize_sql_whitespace(input_sql) == expected
