"""
Unit tests for Pruning (Risk Analysis) module.

Tests the RiskDetector class and RiskIssue dataclass.
"""

import unittest

from sqlopt.stages.pruning.analyzer import RiskDetector, RiskIssue


class RiskIssueTest(unittest.TestCase):
    """Tests for RiskIssue dataclass."""

    def test_to_dict_returns_all_fields(self) -> None:
        """Test that to_dict() returns all fields."""
        issue = RiskIssue(
            sql_key="test.sql",
            risk_type="prefix_wildcard",
            severity="HIGH",
            location={"line": 1, "column": 10},
            suggestion="Use full-text index",
        )
        result = issue.to_dict()

        self.assertEqual(result["sqlKey"], "test.sql")
        self.assertEqual(result["risk_type"], "prefix_wildcard")
        self.assertEqual(result["severity"], "HIGH")
        self.assertEqual(result["location"], {"line": 1, "column": 10})
        self.assertEqual(result["suggestion"], "Use full-text index")

    def test_to_dict_handles_none_location(self) -> None:
        """Test that to_dict() handles None location."""
        issue = RiskIssue(
            sql_key="test.sql",
            risk_type="select_star",
            severity="LOW",
            suggestion="Specify columns",
        )
        result = issue.to_dict()

        self.assertNotIn("location", result)
        self.assertEqual(result["sqlKey"], "test.sql")


class RiskDetectorTest(unittest.TestCase):
    """Tests for RiskDetector class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.detector = RiskDetector()

    def test_detect_prefix_wildcard_high_severity(self) -> None:
        """Test detection of prefix wildcard pattern '%value%'."""
        sql = "SELECT * FROM users WHERE name LIKE '%john'"
        issues = self.detector.detect_prefix_wildcard(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "prefix_wildcard")
        self.assertEqual(issues[0].severity, "HIGH")
        self.assertIn("full-text index", issues[0].suggestion)

    def test_detect_suffix_wildcard_low_severity(self) -> None:
        """Test detection of suffix wildcard pattern 'value%'."""
        sql = "SELECT * FROM users WHERE name LIKE 'john%'"
        issues = self.detector.detect_suffix_wildcard(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "suffix_wildcard")
        self.assertEqual(issues[0].severity, "LOW")
        self.assertIn("covering index", issues[0].suggestion)

    def test_detect_function_wrap_medium_severity(self) -> None:
        """Test detection of function-wrapped columns."""
        sql = "SELECT * FROM users WHERE UPPER(name) = 'JOHN'"
        issues = self.detector.detect_function_wrap(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "function_wrap")
        self.assertEqual(issues[0].severity, "MEDIUM")
        self.assertIn("UPPER", issues[0].suggestion)
        self.assertIn("prevents index usage", issues[0].suggestion)

    def test_detect_function_wrap_lowercase(self) -> None:
        """Test detection of LOWER function wrap."""
        sql = "SELECT * FROM users WHERE LOWER(email) = 'test@example.com'"
        issues = self.detector.detect_function_wrap(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "function_wrap")
        self.assertEqual(issues[0].severity, "MEDIUM")

    def test_detect_select_star(self) -> None:
        """Test detection of SELECT * pattern."""
        sql = "SELECT * FROM users"
        issues = self.detector.detect_select_star(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "select_star")
        self.assertEqual(issues[0].severity, "LOW")
        self.assertIn("Specify only needed columns", issues[0].suggestion)

    def test_detect_select_star_case_insensitive(self) -> None:
        """Test that SELECT * detection is case insensitive."""
        sql = "select * from users"
        issues = self.detector.detect_select_star(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "select_star")

    def test_detect_missing_index(self) -> None:
        """Test detection of WHERE clause without index hint."""
        sql = "SELECT * FROM users WHERE status = 1"
        issues = self.detector.detect_missing_index(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "missing_index")
        self.assertEqual(issues[0].severity, "MEDIUM")
        self.assertIn("index", issues[0].suggestion.lower())

    def test_detect_missing_index_with_hint(self) -> None:
        """Test that index hint suppresses missing index detection."""
        sql = "SELECT * FROM users USE INDEX (idx_status) WHERE status = 1"
        issues = self.detector.detect_missing_index(sql, "test.sql")

        self.assertEqual(len(issues), 0)

    def test_detect_n_plus_1(self) -> None:
        """Test detection of N+1 query pattern."""
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        issues = self.detector.detect_n_plus_1(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "n_plus_1")
        self.assertEqual(issues[0].severity, "HIGH")
        self.assertIn("JOIN", issues[0].suggestion)

    def test_detect_n_plus_1_exists(self) -> None:
        """Test detection of N+1 with EXISTS."""
        sql = "SELECT * FROM users WHERE EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)"
        issues = self.detector.detect_n_plus_1(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].risk_type, "n_plus_1")
        self.assertEqual(issues[0].severity, "HIGH")

    def test_analyze_runs_all_detectors(self) -> None:
        """Test that analyze() runs all detectors."""
        sql = "SELECT * FROM users WHERE name LIKE '%john' AND UPPER(name) = 'JOHN'"
        issues = self.detector.analyze(sql, "test.sql")

        # Should detect multiple issues
        self.assertGreaterEqual(len(issues), 2)
        risk_types = {issue.risk_type for issue in issues}
        self.assertIn("prefix_wildcard", risk_types)
        self.assertIn("function_wrap", risk_types)
        self.assertIn("select_star", risk_types)

    def test_analyze_returns_empty_for_clean_sql(self) -> None:
        """Test that clean SQL produces no false positives."""
        sql = "SELECT id, name FROM users WHERE status = 1"
        issues = self.detector.analyze(sql, "test.sql")

        # Should have no issues - SELECT with specific columns, no wildcards, no function wrap
        # Note: missing_index might still trigger for WHERE without index hint
        # So we check that we don't have false positive risk types
        risk_types = {issue.risk_type for issue in issues}

        # These should NOT be present for clean SQL
        self.assertNotIn("prefix_wildcard", risk_types)
        self.assertNotIn("function_wrap", risk_types)
        self.assertNotIn("n_plus_1", risk_types)

    def test_no_issues_when_no_match(self) -> None:
        """Test that detectors return empty list when no pattern matches."""
        sql = "SELECT id, name FROM users WHERE id = 1"

        prefix_issues = self.detector.detect_prefix_wildcard(sql, "test.sql")
        self.assertEqual(len(prefix_issues), 0)

        suffix_issues = self.detector.detect_suffix_wildcard(sql, "test.sql")
        self.assertEqual(len(suffix_issues), 0)

        func_issues = self.detector.detect_function_wrap(sql, "test.sql")
        self.assertEqual(len(func_issues), 0)

        n_plus_1_issues = self.detector.detect_n_plus_1(sql, "test.sql")
        self.assertEqual(len(n_plus_1_issues), 0)


class RiskDetectorSeverityTest(unittest.TestCase):
    """Test severity levels for different risk types."""

    def test_prefix_wildcard_is_high(self) -> None:
        """Verify prefix wildcard has HIGH severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users WHERE name LIKE '%john'"
        issues = detector.detect_prefix_wildcard(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "HIGH")

    def test_suffix_wildcard_is_low(self) -> None:
        """Verify suffix wildcard has LOW severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users WHERE name LIKE 'john%'"
        issues = detector.detect_suffix_wildcard(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "LOW")

    def test_function_wrap_is_medium(self) -> None:
        """Verify function wrap has MEDIUM severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users WHERE UPPER(name) = 'JOHN'"
        issues = detector.detect_function_wrap(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "MEDIUM")

    def test_select_star_is_low(self) -> None:
        """Verify SELECT * has LOW severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users"
        issues = detector.detect_select_star(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "LOW")

    def test_missing_index_is_medium(self) -> None:
        """Verify missing index has MEDIUM severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users WHERE status = 1"
        issues = detector.detect_missing_index(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "MEDIUM")

    def test_n_plus_1_is_high(self) -> None:
        """Verify N+1 pattern has HIGH severity."""
        detector = RiskDetector()
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        issues = detector.detect_n_plus_1(sql, "test.sql")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "HIGH")


if __name__ == "__main__":
    unittest.main()
