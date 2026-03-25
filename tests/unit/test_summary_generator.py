"""Tests for summary_generator module."""

import pytest
from sqlopt.common.summary_generator import (
    StageSummary,
    generate_summary_markdown,
    truncate_text,
)


class TestTruncateText:
    """Test truncate_text utility function."""

    def test_text_shorter_than_max_chars_returns_unchanged(self):
        """Text shorter than max_chars should return unchanged."""
        text = "short text"
        result = truncate_text(text, max_chars=1024)
        assert result == "short text"

    def test_text_equal_to_max_chars_returns_unchanged(self):
        """Text equal to max_chars should return unchanged."""
        text = "a" * 1024
        result = truncate_text(text, max_chars=1024)
        assert result == "a" * 1024

    def test_text_longer_than_max_chars_gets_truncated(self):
        """Text longer than max_chars gets truncated with suffix."""
        text = "a" * 2000
        result = truncate_text(text, max_chars=1024)
        assert result == "a" * 1024 + "... (truncated)"

    def test_default_max_chars_is_1024(self):
        """Default max_chars should be 1024."""
        short_text = "a" * 500
        result = truncate_text(short_text)
        assert result == short_text

        long_text = "a" * 2000
        result = truncate_text(long_text)
        assert result == "a" * 1024 + "... (truncated)"

    def test_custom_max_chars_parameter(self):
        """Custom max_chars parameter should work correctly."""
        text = "hello world"
        result = truncate_text(text, max_chars=5)
        assert result == "hello... (truncated)"


class TestStageSummary:
    """Test StageSummary dataclass."""

    def test_all_fields_are_stored(self):
        """Test all fields are properly stored."""
        summary = StageSummary(
            stage_name="test-stage",
            run_id="run-abc",
            duration_seconds=1.5,
            sql_units_count=10,
            branches_count=25,
            files_count=5,
            file_size_bytes=1024000,
        )
        assert summary.stage_name == "test-stage"
        assert summary.run_id == "run-abc"
        assert summary.duration_seconds == 1.5
        assert summary.sql_units_count == 10
        assert summary.branches_count == 25
        assert summary.files_count == 5
        assert summary.file_size_bytes == 1024000

    def test_errors_default_is_empty_list(self):
        """Test errors defaults to empty list."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=0.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
        )
        assert summary.errors == []
        assert isinstance(summary.errors, list)

    def test_warnings_default_is_empty_list(self):
        """Test warnings defaults to empty list."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=0.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
        )
        assert summary.warnings == []
        assert isinstance(summary.warnings, list)

    def test_errors_can_be_set_explicitly(self):
        """Test errors can be set to non-empty list."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=0.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=["error 1", "error 2"],
        )
        assert summary.errors == ["error 1", "error 2"]

    def test_warnings_can_be_set_explicitly(self):
        """Test warnings can be set to non-empty list."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=0.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            warnings=["warning 1"],
        )
        assert summary.warnings == ["warning 1"]


class TestGenerateSummaryMarkdown:
    """Test generate_summary_markdown function."""

    def test_header_contains_stage_name_upper_and_stage_summary(self):
        """Header should contain stage_name.upper() and 'Stage Summary'."""
        summary = StageSummary(
            stage_name="parse",
            run_id="run-123",
            duration_seconds=10.0,
            sql_units_count=5,
            branches_count=15,
            files_count=3,
            file_size_bytes=50000,
        )
        result = generate_summary_markdown(summary)
        assert "# PARSE Stage Summary" in result

    def test_run_id_appears_in_output(self):
        """Run ID should appear in output."""
        summary = StageSummary(
            stage_name="init",
            run_id="run-abc-999",
            duration_seconds=5.0,
            sql_units_count=10,
            branches_count=0,
            files_count=2,
            file_size_bytes=10000,
        )
        result = generate_summary_markdown(summary)
        assert "**Run ID:** run-abc-999" in result

    def test_duration_appears_in_output(self):
        """Duration should appear in output with 2 decimal places."""
        summary = StageSummary(
            stage_name="optimize",
            run_id="run-1",
            duration_seconds=3.14159,
            sql_units_count=8,
            branches_count=20,
            files_count=4,
            file_size_bytes=80000,
        )
        result = generate_summary_markdown(summary)
        assert "**Duration:** 3.14 seconds" in result

    def test_statistics_table_has_sql_units(self):
        """Statistics table should have SQL Units metric."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=42,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
        )
        result = generate_summary_markdown(summary)
        assert "| SQL Units | 42 |" in result

    def test_statistics_table_has_branches(self):
        """Statistics table should have Branches metric."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=100,
            files_count=0,
            file_size_bytes=0,
        )
        result = generate_summary_markdown(summary)
        assert "| Branches | 100 |" in result

    def test_statistics_table_has_files(self):
        """Statistics table should have Files metric."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=7,
            file_size_bytes=0,
        )
        result = generate_summary_markdown(summary)
        assert "| Files | 7 |" in result

    def test_statistics_table_has_file_size_bytes(self):
        """Statistics table should have File Size metric with formatted bytes."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=1234567,
        )
        result = generate_summary_markdown(summary)
        assert "| File Size | 1,234,567 bytes |" in result

    def test_data_contracts_section_present(self):
        """Data Contracts section should be present."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
        )
        result = generate_summary_markdown(summary)
        assert "## Data Contracts" in result

    def test_errors_section_not_present_when_empty(self):
        """Errors section should NOT appear when errors list is empty."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=[],
        )
        result = generate_summary_markdown(summary)
        assert "## Errors" not in result

    def test_errors_section_present_when_non_empty(self):
        """Errors section should appear when errors list is non-empty."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=["Something went wrong"],
        )
        result = generate_summary_markdown(summary)
        assert "## Errors" in result
        assert "Something went wrong" in result

    def test_warnings_section_not_present_when_empty(self):
        """Warnings section should NOT appear when warnings list is empty."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            warnings=[],
        )
        result = generate_summary_markdown(summary)
        assert "## Warnings" not in result

    def test_warnings_section_present_when_non_empty(self):
        """Warnings section should appear when warnings list is non-empty."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            warnings=["Low disk space"],
        )
        result = generate_summary_markdown(summary)
        assert "## Warnings" in result
        assert "Low disk space" in result

    def test_error_messages_truncated_at_500_chars(self):
        """Error messages should be truncated at 500 characters."""
        long_error = "x" * 1000
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=[long_error],
        )
        result = generate_summary_markdown(summary)
        # The truncated error should end with "... (truncated)"
        # 500 chars + suffix
        assert "xxx... (truncated)" in result or result.count("x") == 500

    def test_output_respects_50kb_max_size(self):
        """Output should be truncated if it exceeds 50KB."""
        # Create a summary with a very large error to push output over 50KB
        large_error = "x" * 100000  # 100KB of data
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=[large_error] * 10,  # 1MB of errors
        )
        result = generate_summary_markdown(summary)
        assert len(result) <= 50 * 1024 + 50  # Allow small margin

    def test_multiple_errors_numbered(self):
        """Multiple errors should be numbered."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            errors=["error one", "error two", "error three"],
        )
        result = generate_summary_markdown(summary)
        assert "1. error one" in result
        assert "2. error two" in result
        assert "3. error three" in result

    def test_multiple_warnings_numbered(self):
        """Multiple warnings should be numbered."""
        summary = StageSummary(
            stage_name="test",
            run_id="run-1",
            duration_seconds=1.0,
            sql_units_count=0,
            branches_count=0,
            files_count=0,
            file_size_bytes=0,
            warnings=["warn a", "warn b"],
        )
        result = generate_summary_markdown(summary)
        assert "1. warn a" in result
        assert "2. warn b" in result
