from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.configuration.defaults import apply_minimal_defaults


class ConfigDefaultsTest(unittest.TestCase):
    def test_apply_minimal_defaults_populates_internal_runtime_and_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_defaults_") as td:
            cfg: dict = {
                "project": {"root_path": "."},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql", "dsn": "postgresql://dummy"},
                "llm": {"provider": "opencode_builtin"},
            }
            apply_minimal_defaults(cfg, config_path=Path(td) / "sqlopt.yml")

        self.assertEqual(cfg["apply"]["mode"], "PATCH_ONLY")
        self.assertTrue(cfg["llm"]["enabled"])
        self.assertEqual(cfg["validate"]["selection_mode"], "patchability_first")
        self.assertEqual(cfg["verification"]["critical_output_policy"], "warn")
        self.assertIn("stage_timeout_ms", cfg["runtime"])

    def test_apply_minimal_defaults_preserves_resolved_internal_overrides(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_defaults_") as td:
            cfg: dict = {
                "project": {"root_path": "."},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {"platform": "postgresql", "dsn": "postgresql://dummy"},
                "llm": {"provider": "opencode_builtin"},
                "validate": {"db_reachable": False},
                "runtime": {"stage_retry_backoff_ms": 250},
            }
            apply_minimal_defaults(cfg, config_path=Path(td) / "config.resolved.json")

        self.assertFalse(cfg["validate"]["db_reachable"])
        self.assertEqual(cfg["validate"]["selection_mode"], "patchability_first")
        self.assertEqual(cfg["runtime"]["stage_retry_backoff_ms"], 250)
        self.assertIn("preflight", cfg["runtime"]["stage_timeout_ms"])


if __name__ == "__main__":
    unittest.main()
