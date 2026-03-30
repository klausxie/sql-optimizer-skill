"""Tests for removed/deprecated config key compatibility handling."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.config import load_config
from sqlopt.configuration.common import check_removed_keys


class ImprovedRemovedKeysTest(unittest.TestCase):
    """Test removed key detection hints and compatibility behavior."""

    def test_check_removed_keys_returns_warnings_with_hints(self) -> None:
        """Test that check_removed_keys returns helpful hints."""
        cfg = {"validate": {}, "policy": {}}
        warnings = check_removed_keys(cfg)

        self.assertEqual(len(warnings), 2)
        # Check that warnings contain keys and hints
        keys = [w[0] for w in warnings]
        hints = [w[1] for w in warnings]

        self.assertIn("policy", keys)
        self.assertIn("validate", keys)
        # Check that hints are helpful
        for hint in hints:
            self.assertIn("auto-injected", hint.lower())
            self.assertIn("remove", hint.lower())

    def test_check_removed_keys_returns_empty_for_valid_config(self) -> None:
        """Test that check_removed_keys returns empty list for valid config."""
        cfg = {
            "project": {"root_path": "."},
            "scan": {"mapper_globs": ["**/*.xml"]},
            "db": {"platform": "postgresql", "dsn": "postgresql://localhost/db"},
            "llm": {"provider": "opencode_builtin"},
        }
        warnings = check_removed_keys(cfg)
        self.assertEqual(len(warnings), 0)

    def test_removed_key_is_ignored_when_loading(self) -> None:
        """Removed keys should be ignored for backward compatibility."""
        td = tempfile.TemporaryDirectory(prefix="sqlopt_removed_key_")
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
        self.assertTrue(loaded["validate"]["db_reachable"])

    def test_multiple_removed_keys_are_all_ignored(self) -> None:
        """Multiple removed keys should all be ignored."""
        td = tempfile.TemporaryDirectory(prefix="sqlopt_multiple_removed_")
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
        self.assertEqual(loaded["policy"]["cost_threshold_pct"], 0)
        self.assertEqual(loaded["runtime"]["stage_retry_backoff_ms"], 1000)
        self.assertTrue(loaded["validate"]["db_reachable"])

    def test_nested_removed_key_is_ignored(self) -> None:
        """Nested removed keys should be ignored."""
        td = tempfile.TemporaryDirectory(prefix="sqlopt_nested_removed_")
        self.addCleanup(td.cleanup)

        cfg_path = Path(td.name) / "sqlopt.yml"
        cfg_path.write_text(
            """
project:
  root_path: .
scan:
  mapper_globs:
    - src/**/*.xml
  java_scanner:
    jar_path: /tmp/scanner.jar
db:
  platform: postgresql
  dsn: postgresql://localhost/db
llm:
  provider: opencode_builtin
""",
            encoding="utf-8",
        )

        loaded = load_config(cfg_path)
        self.assertNotIn("java_scanner", loaded["scan"])


if __name__ == "__main__":
    unittest.main()
