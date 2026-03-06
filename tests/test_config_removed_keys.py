from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.config import load_config
from sqlopt.errors import ConfigError


BASE_YAML = """\
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost:5432/demo
llm:
  provider: opencode_builtin
"""


class ConfigRemovedKeysTest(unittest.TestCase):
    def _write_cfg(self, extra: str) -> Path:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cfg_removed_")
        self.addCleanup(td.cleanup)
        cfg = Path(td.name) / "sqlopt.yml"
        cfg.write_text(BASE_YAML + extra, encoding="utf-8")
        return cfg

    def test_removed_root_sections_are_rejected(self) -> None:
        for section in ("validate", "policy", "apply", "patch", "diagnostics", "runtime", "verification"):
            cfg = self._write_cfg(f"{section}: {{}}\n")
            with self.assertRaises(ConfigError):
                load_config(cfg)

    def test_removed_scan_keys_are_rejected(self) -> None:
        cfg = self._write_cfg(
            """\
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
  java_scanner:
    jar_path: /tmp/demo.jar
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_removed_db_timeout_key_is_rejected(self) -> None:
        cfg = self._write_cfg(
            """\
db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost:5432/demo
  statement_timeout_ms: 5000
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_db_schema_is_accepted(self) -> None:
        cfg = self._write_cfg(
            """\
db:
  platform: postgresql
  dsn: postgresql://user:pass@localhost:5432/demo
  schema: public
"""
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["db"]["schema"], "public")

    def test_removed_llm_keys_are_rejected(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  provider: opencode_builtin
  retry:
    enabled: true
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_minimal_config_loads_and_internal_defaults_are_injected(self) -> None:
        loaded = load_config(self._write_cfg(""))
        self.assertEqual(loaded["llm"]["provider"], "opencode_builtin")
        self.assertEqual(loaded["apply"]["mode"], "PATCH_ONLY")
        self.assertFalse(loaded["validate"]["db_reachable"])
        self.assertEqual(loaded["verification"]["critical_output_policy"], "warn")
        self.assertTrue(loaded["report"]["enabled"])

    def test_direct_openai_provider_requires_fields(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  provider: direct_openai_compatible
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_direct_openai_provider_accepts_complete_fields(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  provider: direct_openai_compatible
  api_base: https://example.com/v1
  api_key: k
  api_model: m
"""
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["llm"]["provider"], "direct_openai_compatible")
        self.assertEqual(loaded["llm"]["api_model"], "m")

    def test_report_enabled_can_be_overridden(self) -> None:
        cfg = self._write_cfg(
            """\
report:
  enabled: false
"""
        )
        loaded = load_config(cfg)
        self.assertFalse(loaded["report"]["enabled"])

    def test_config_version_alias_is_normalized(self) -> None:
        cfg = self._write_cfg("config_version: 1.0\n")
        loaded = load_config(cfg)
        self.assertEqual(loaded["config_version"], "v1")

    def test_config_version_rejects_unknown_version(self) -> None:
        cfg = self._write_cfg("config_version: v2\n")
        with self.assertRaises(ConfigError):
            load_config(cfg)


if __name__ == "__main__":
    unittest.main()
