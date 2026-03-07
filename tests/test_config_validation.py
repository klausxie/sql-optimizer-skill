"""Tests for configuration validation module."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from sqlopt.configuration.validation import (
    SECTION_ALLOWED_KEYS,
    validate_resolved_config,
    validate_section_keys,
    validate_types,
    validate_user_config,
)
from sqlopt.errors import ConfigError


BASE_CONFIG = {
    "project": {"root_path": "."},
    "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
    "db": {"platform": "postgresql", "dsn": "postgresql://user:pass@localhost:5432/demo"},
    "llm": {"provider": "opencode_builtin"},
    "report": {"enabled": True},
}


class ValidationModuleTest(unittest.TestCase):
    """Test configuration validation functions."""

    def test_section_allowed_keys_defined(self) -> None:
        """Test that SECTION_ALLOWED_KEYS is properly defined."""
        self.assertIn("project", SECTION_ALLOWED_KEYS)
        self.assertIn("scan", SECTION_ALLOWED_KEYS)
        self.assertIn("db", SECTION_ALLOWED_KEYS)
        self.assertIn("llm", SECTION_ALLOWED_KEYS)
        self.assertIn("report", SECTION_ALLOWED_KEYS)

    def test_validate_section_keys_accepts_valid_config(self) -> None:
        """Test that valid configuration passes section key validation."""
        cfg = copy.deepcopy(BASE_CONFIG)
        validate_section_keys(cfg)  # Should not raise

    def test_validate_section_keys_rejects_unknown_keys(self) -> None:
        """Test that unknown keys in sections are rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["scan"]["unknown_key"] = "value"
        with self.assertRaises(ConfigError) as ctx:
            validate_section_keys(cfg)
        self.assertIn("scan.unknown_key", str(ctx.exception))

    def test_validate_types_accepts_valid_config(self) -> None:
        """Test that valid configuration passes type validation."""
        cfg = copy.deepcopy(BASE_CONFIG)
        validate_types(cfg)  # Should not raise

    def test_validate_types_rejects_empty_root_path(self) -> None:
        """Test that empty root_path is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["project"]["root_path"] = ""
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("root_path", str(ctx.exception))

    def test_validate_types_rejects_empty_mapper_globs(self) -> None:
        """Test that empty mapper_globs is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["scan"]["mapper_globs"] = []
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("mapper_globs", str(ctx.exception))

    def test_validate_types_rejects_invalid_platform(self) -> None:
        """Test that invalid database platform is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["db"]["platform"] = "oracle"
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("platform", str(ctx.exception))

    def test_validate_types_accepts_postgresql(self) -> None:
        """Test that postgresql platform is accepted."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["db"]["platform"] = "postgresql"
        validate_types(cfg)  # Should not raise

    def test_validate_types_accepts_mysql(self) -> None:
        """Test that mysql platform is accepted."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["db"]["platform"] = "mysql"
        validate_types(cfg)  # Should not raise

    def test_validate_types_rejects_empty_dsn(self) -> None:
        """Test that empty DSN is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["db"]["dsn"] = ""
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("dsn", str(ctx.exception))

    def test_validate_types_rejects_invalid_provider(self) -> None:
        """Test that invalid LLM provider is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["llm"]["provider"] = "invalid_provider"
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("provider", str(ctx.exception))

    def test_validate_types_accepts_all_valid_providers(self) -> None:
        """Test that all valid LLM providers are accepted."""
        for provider in ("opencode_run", "opencode_builtin", "heuristic", "direct_openai_compatible"):
            cfg = copy.deepcopy(BASE_CONFIG)
            cfg["llm"]["provider"] = provider
            if provider == "direct_openai_compatible":
                cfg["llm"]["api_base"] = "https://api.example.com"
                cfg["llm"]["api_key"] = "test_key"
                cfg["llm"]["api_model"] = "test_model"
            validate_types(cfg)  # Should not raise

    def test_validate_types_requires_api_keys_for_direct_openai(self) -> None:
        """Test that direct_openai_compatible requires API keys."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["llm"]["provider"] = "direct_openai_compatible"
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("api_", str(ctx.exception))

    def test_validate_types_rejects_negative_timeout(self) -> None:
        """Test that negative timeout is rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["llm"]["timeout_ms"] = -1
        with self.assertRaises(ConfigError) as ctx:
            validate_types(cfg)
        self.assertIn("timeout_ms", str(ctx.exception))

    def test_validate_user_config_accepts_valid_config(self) -> None:
        """Test that valid user configuration is accepted."""
        cfg = copy.deepcopy(BASE_CONFIG)
        validate_user_config(cfg)  # Should not raise

    def test_validate_user_config_rejects_removed_keys(self) -> None:
        """Test that removed keys are rejected in user config."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["validate"] = {}
        with self.assertRaises(ConfigError) as ctx:
            validate_user_config(cfg)
        # Check that error message contains helpful information
        error_msg = str(ctx.exception)
        self.assertIn("validate", error_msg)
        self.assertIn("no longer supported", error_msg.lower())

    def test_validate_user_config_rejects_unknown_root_keys(self) -> None:
        """Test that unknown root keys are rejected."""
        cfg = copy.deepcopy(BASE_CONFIG)
        cfg["unknown_section"] = {}
        with self.assertRaises(ConfigError) as ctx:
            validate_user_config(cfg)
        self.assertIn("unknown", str(ctx.exception))

    def test_validate_resolved_config_accepts_internal_sections(self) -> None:
        """Test that resolved config accepts internal sections."""
        cfg = copy.deepcopy(BASE_CONFIG)
        # Add internal sections that would be present in resolved config
        cfg["validate"] = {}
        cfg["policy"] = {}
        cfg["runtime"] = {}
        # Resolved config only validates types, not key restrictions
        validate_resolved_config(cfg)  # Should not raise


if __name__ == "__main__":
    unittest.main()
