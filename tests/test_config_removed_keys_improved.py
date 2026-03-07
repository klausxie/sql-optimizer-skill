"""Tests for improved removed keys error messages."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.config import load_config
from sqlopt.configuration.common import check_removed_keys
from sqlopt.errors import ConfigError


class ImprovedRemovedKeysTest(unittest.TestCase):
    """Test improved error messages for removed configuration keys."""

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

    def test_removed_key_error_includes_hint(self) -> None:
        """Test that ConfigError for removed keys includes helpful hint."""
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

        with self.assertRaises(ConfigError) as ctx:
            load_config(cfg_path)

        error_msg = str(ctx.exception)
        # Check that error message contains the key
        self.assertIn("validate", error_msg)
        # Check that error message contains a hint
        self.assertIn("Hint:", error_msg)
        self.assertIn("auto-injected", error_msg.lower())

    def test_multiple_removed_keys_shows_count(self) -> None:
        """Test that multiple removed keys show total count."""
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

        with self.assertRaises(ConfigError) as ctx:
            load_config(cfg_path)

        error_msg = str(ctx.exception)
        # Check that error message mentions multiple keys
        self.assertIn("removed key(s)", error_msg.lower())

    def test_nested_removed_key_error_includes_hint(self) -> None:
        """Test that nested removed keys also get helpful hints."""
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

        with self.assertRaises(ConfigError) as ctx:
            load_config(cfg_path)

        error_msg = str(ctx.exception)
        # Check that error message contains the nested key
        self.assertIn("scan.java_scanner", error_msg)
        # Check that error message contains a hint
        self.assertIn("Hint:", error_msg)


if __name__ == "__main__":
    unittest.main()
