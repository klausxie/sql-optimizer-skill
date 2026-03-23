"""
Unit tests for Scanner's statement_types filtering.

Tests verify that the Scanner class correctly handles the statement_types
configuration option for filtering SQL statement types to scan.
"""

from __future__ import annotations

import pytest

from sqlopt.application.v9_stages.init import Scanner


class TestScannerStatementTypes:
    """Test cases for Scanner's statement_types configuration."""

    def test_default_statement_types_select_only(self) -> None:
        """Scanner with empty config defaults to SELECT only."""
        scanner = Scanner({})
        assert scanner.statement_tags == {"select"}

    def test_custom_statement_types_filtering(self) -> None:
        """Scanner with custom statement_types uses provided values."""
        config = {"scan": {"statement_types": ["SELECT", "INSERT"]}}
        scanner = Scanner(config)
        assert scanner.statement_tags == {"select", "insert"}

    def test_case_insensitive_statement_types(self) -> None:
        """Scanner handles statement_types case-insensitively."""
        config = {"scan": {"statement_types": ["select", "INSERT"]}}
        scanner = Scanner(config)
        assert scanner.statement_tags == {"select", "insert"}

    def test_empty_statement_types(self) -> None:
        """Scanner with empty statement_types has empty tags (no statements scanned)."""
        config = {"scan": {"statement_types": []}}
        scanner = Scanner(config)
        assert scanner.statement_tags == set()

    def test_all_statement_types(self) -> None:
        """Scanner with all statement types scans all four types."""
        config = {"scan": {"statement_types": ["SELECT", "INSERT", "UPDATE", "DELETE"]}}
        scanner = Scanner(config)
        assert scanner.statement_tags == {"select", "insert", "update", "delete"}

    def test_none_config_defaults_to_select(self) -> None:
        """Scanner with None config defaults to SELECT only."""
        scanner = Scanner(None)
        assert scanner.statement_tags == {"select"}

    def test_statement_types_with_whitespace(self) -> None:
        """Scanner strips whitespace from statement_types."""
        config = {"scan": {"statement_types": ["  SELECT  ", "  INSERT  "]}}
        scanner = Scanner(config)
        assert scanner.statement_tags == {"select", "insert"}

    def test_duplicate_statement_types_deduplicated(self) -> None:
        """Scanner deduplicates statement_types."""
        config = {"scan": {"statement_types": ["SELECT", "select", "SELECT"]}}
        scanner = Scanner(config)
        assert scanner.statement_tags == {"select"}
