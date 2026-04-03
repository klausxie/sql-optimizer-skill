"""
Tests for reason code registry.
"""

import pytest
from sqlopt.reason_codes import (
    ReasonCode,
    get_reason_code,
    format_error_message,
    get_codes_by_category,
    get_codes_by_severity,
    REASON_CODES,
)


class TestReasonCodeRegistry:
    """Test reason code registry and helper functions."""

    def test_all_codes_registered(self):
        """Verify all expected reason codes are registered."""
        # Should have the full registry, including patch contract guards.
        assert len(REASON_CODES) >= 41

        # Check some key codes exist
        expected_codes = [
            "RUNTIME_STAGE_TIMEOUT",
            "RUNTIME_RETRY_EXHAUSTED",
            "PREFLIGHT_MISSING_SCANNER_JAR",
            "SCAN_JAVA_SCANNER_FAILED",
            "OPTIMIZE_LLM_TIMEOUT",
            "VALIDATE_DB_UNREACHABLE",
            "PATCH_TEMPLATE_REWRITE_UNSAFE",
            "PATCH_REPLAY_CONTRACT_MISSING",
            "PATCH_TARGET_CONTRACT_MISSING",
        ]
        for code in expected_codes:
            assert code in REASON_CODES, f"Expected code {code} not found"

    def test_get_reason_code_success(self):
        """Test retrieving existing reason code."""
        code = get_reason_code("RUNTIME_STAGE_TIMEOUT")
        assert isinstance(code, ReasonCode)
        assert code.code == "RUNTIME_STAGE_TIMEOUT"
        assert code.category == "runtime"
        assert code.severity == "retryable"
        assert len(code.description) > 0
        assert len(code.user_message) > 0

    def test_get_reason_code_not_found(self):
        """Test retrieving non-existent reason code."""
        code = get_reason_code("NONEXISTENT_CODE")
        assert code is None

    def test_format_error_message_with_context(self):
        """Test formatting error message with context."""
        msg = format_error_message(
            "VALIDATE_DB_UNREACHABLE",
            context={"sql_key": "demo.user.findUsers", "phase": "validate"}
        )
        assert "[DEGRADABLE]" in msg
        assert "Cannot connect to database" in msg
        assert "demo.user.findUsers" in msg
        assert "validate" in msg

    def test_format_error_message_without_context(self):
        """Test formatting error message without context."""
        msg = format_error_message("SCAN_JAVA_SCANNER_FAILED")
        assert "SCAN_JAVA_SCANNER_FAILED" in msg
        assert "Java scanner execution failed" in msg

    def test_format_error_message_unknown_code(self):
        """Test formatting message for unknown code."""
        msg = format_error_message("UNKNOWN_CODE")
        assert "UNKNOWN_CODE" in msg
        assert "Unknown error" in msg

    def test_get_codes_by_category_runtime(self):
        """Test filtering codes by runtime category."""
        codes = get_codes_by_category("runtime")
        assert len(codes) >= 2
        assert all(c.category == "runtime" for c in codes)
        code_names = [c.code for c in codes]
        assert "RUNTIME_STAGE_TIMEOUT" in code_names
        assert "RUNTIME_STAGE_RETRY_EXHAUSTED" in code_names

    def test_get_codes_by_category_scan(self):
        """Test filtering codes by scan category."""
        codes = get_codes_by_category("scan")
        assert len(codes) >= 10
        assert all(c.category == "scan" for c in codes)

    def test_get_codes_by_category_empty(self):
        """Test filtering with non-existent category."""
        codes = get_codes_by_category("nonexistent")
        assert len(codes) == 0

    def test_get_codes_by_severity_fatal(self):
        """Test filtering codes by fatal severity."""
        codes = get_codes_by_severity("fatal")
        assert len(codes) > 0
        assert all(c.severity == "fatal" for c in codes)

    def test_get_codes_by_severity_retryable(self):
        """Test filtering codes by retryable severity."""
        codes = get_codes_by_severity("retryable")
        assert len(codes) > 0
        assert all(c.severity == "retryable" for c in codes)

    def test_get_codes_by_severity_degradable(self):
        """Test filtering codes by degradable severity."""
        codes = get_codes_by_severity("degradable")
        assert len(codes) > 0
        assert all(c.severity == "degradable" for c in codes)

    def test_reason_code_immutable(self):
        """Test that ReasonCode is immutable."""
        code = get_reason_code("RUNTIME_STAGE_TIMEOUT")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            code.code = "MODIFIED"

    def test_all_codes_have_required_fields(self):
        """Test that all codes have non-empty required fields."""
        for code_name, code in REASON_CODES.items():
            assert code.code == code_name
            assert len(code.category) > 0
            assert len(code.severity) > 0
            assert len(code.description) > 0
            assert len(code.user_message) > 0
            assert code.severity in ["fatal", "retryable", "degradable"]

    def test_category_distribution(self):
        """Test that codes are distributed across categories."""
        categories = set(c.category for c in REASON_CODES.values())
        expected_categories = {
            "runtime", "preflight", "scan", "optimize",
            "validate", "patch", "platform", "verification"
        }
        assert categories == expected_categories

    def test_severity_distribution(self):
        """Test that codes use all severity levels."""
        severities = set(c.severity for c in REASON_CODES.values())
        assert "fatal" in severities
        assert "retryable" in severities
        assert "degradable" in severities

    def test_patch_contract_guard_codes_are_patch_degradable(self):
        """Patch contract guard codes should be patch-surface degradable outcomes."""
        replay_missing = get_reason_code("PATCH_REPLAY_CONTRACT_MISSING")
        target_missing = get_reason_code("PATCH_TARGET_CONTRACT_MISSING")
        family_missing = get_reason_code("PATCH_FAMILY_SPEC_MISSING")

        assert replay_missing is not None
        assert replay_missing.category == "patch"
        assert replay_missing.severity == "degradable"

        assert target_missing is not None
        assert target_missing.category == "patch"
        assert target_missing.severity == "degradable"

        assert family_missing is not None
        assert family_missing.category == "patch"
        assert family_missing.severity == "degradable"
