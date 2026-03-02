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


if __name__ == "__main__":
    unittest.main()
