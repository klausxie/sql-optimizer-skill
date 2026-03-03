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
policy:
  require_perf_improvement: false
  cost_threshold_pct: 0
  allow_seq_scan_if_rows_below: 0
  semantic_strict_mode: true
runtime:
  profile: fast
llm:
  enabled: false
"""


class ConfigRemovedKeysTest(unittest.TestCase):
    def _write_cfg(self, extra: str) -> Path:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cfg_removed_")
        self.addCleanup(td.cleanup)
        cfg = Path(td.name) / "sqlopt.yml"
        cfg.write_text(BASE_YAML + extra, encoding="utf-8")
        return cfg

    def test_removed_validate_key_rejected(self) -> None:
        cfg = self._write_cfg(
            """\
validate:
  sample_count: 50
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_removed_llm_key_rejected(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  enabled: true
  provider: opencode_run
  strict_required: true
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_direct_openai_provider_requires_fields(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  enabled: true
  provider: direct_openai_compatible
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_direct_openai_provider_accepts_complete_fields(self) -> None:
        cfg = self._write_cfg(
            """\
llm:
  enabled: true
  provider: direct_openai_compatible
  api_base: https://example.com/v1
  api_key: k
  api_model: m
  api_timeout_ms: 5000
  api_headers:
    x-env: prod
"""
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["llm"]["provider"], "direct_openai_compatible")
        self.assertEqual(loaded["llm"]["api_model"], "m")

    def test_verification_gate_policy_defaults_warn_and_accepts_block(self) -> None:
        cfg = self._write_cfg(
            """\
verification:
  critical_output_policy: block
"""
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["verification"]["critical_output_policy"], "block")

        default_cfg = self._write_cfg("")
        default_loaded = load_config(default_cfg)
        self.assertFalse(default_loaded["verification"]["enforce_verified_outputs"])
        self.assertIsNone(default_loaded["verification"]["critical_output_policy"])

    def test_verification_gate_policy_rejects_invalid_value(self) -> None:
        cfg = self._write_cfg(
            """\
verification:
  critical_output_policy: strict
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)


if __name__ == "__main__":
    unittest.main()
