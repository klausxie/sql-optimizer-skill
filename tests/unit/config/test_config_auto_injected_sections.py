"""Tests for auto-injected section compatibility handling."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.config import load_config
from sqlopt.configuration.common import strip_auto_injected_sections


class AutoInjectedSectionsTest(unittest.TestCase):
    """Test auto-injected section stripping and compatibility behavior."""

    def test_strip_auto_injected_sections_removes_known_sections(self) -> None:
        """Test that strip_auto_injected_sections removes known sections."""
        cfg = {"validate": {}, "policy": {}, "project": {"root_path": "."}}
        removed = strip_auto_injected_sections(cfg)

        self.assertEqual(set(removed), {"validate", "policy"})
        self.assertNotIn("validate", cfg)
        self.assertNotIn("policy", cfg)
        self.assertIn("project", cfg)

    def test_strip_auto_injected_sections_returns_empty_for_clean_config(self) -> None:
        """Test that strip_auto_injected_sections returns empty list for clean config."""
        cfg = {
            "project": {"root_path": "."},
            "scan": {"mapper_globs": ["**/*.xml"]},
            "db": {"platform": "postgresql", "dsn": "postgresql://localhost/db"},
            "llm": {"provider": "opencode_builtin"},
        }
        removed = strip_auto_injected_sections(cfg)
        self.assertEqual(len(removed), 0)

    def test_removed_section_is_ignored_when_loading(self) -> None:
        """Removed sections should be ignored for backward compatibility."""
        td = tempfile.TemporaryDirectory(prefix="sqlopt_removed_section_")
        self.addCleanup(td.cleanup)

        cfg_path = Path(td.name) / "sqlopt.yml"
        cfg_path.write_text(
            """
project:
  root_path: .
scan:
  mapper_globs:
    - src/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://localhost/db
llm:
  provider: opencode_builtin
validate:
  sample_count: 100
""",
            encoding="utf-8",
        )

        loaded = load_config(cfg_path)
        # validate section is auto-injected with defaults
        self.assertTrue(loaded["validate"]["db_reachable"])

    def test_multiple_removed_sections_are_all_ignored(self) -> None:
        """Multiple removed sections should all be ignored."""
        td = tempfile.TemporaryDirectory(prefix="sqlopt_multiple_sections_")
        self.addCleanup(td.cleanup)

        cfg_path = Path(td.name) / "sqlopt.yml"
        cfg_path.write_text(
            """
project:
  root_path: .
scan:
  mapper_globs:
    - src/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://localhost/db
llm:
  provider: opencode_builtin
validate: {}
policy: {}
runtime: {}
""",
            encoding="utf-8",
        )

        loaded = load_config(cfg_path)
        # Sections are auto-injected with defaults
        self.assertEqual(loaded["policy"]["cost_threshold_pct"], 0)
        self.assertEqual(loaded["runtime"]["stage_retry_backoff_ms"], 1000)
        self.assertTrue(loaded["validate"]["db_reachable"])


if __name__ == "__main__":
    unittest.main()