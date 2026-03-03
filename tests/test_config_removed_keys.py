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

    def test_diagnostics_defaults_and_overrides_are_loaded(self) -> None:
        cfg = self._write_cfg(
            """\
diagnostics:
  severity_overrides:
    SELECT_STAR: error
  disabled_rules:
    - FULL_SCAN_RISK
"""
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["diagnostics"]["rulepacks"], [{"builtin": "core"}, {"builtin": "performance"}])
        self.assertEqual(loaded["diagnostics"]["severity_overrides"]["SELECT_STAR"], "error")
        self.assertEqual(loaded["diagnostics"]["disabled_rules"], ["FULL_SCAN_RISK"])

    def test_diagnostics_reject_invalid_rulepack(self) -> None:
        cfg = self._write_cfg(
            """\
diagnostics:
  rulepacks:
    - builtin: custom
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_diagnostics_reject_invalid_override_severity(self) -> None:
        cfg = self._write_cfg(
            """\
diagnostics:
  severity_overrides:
    SELECT_STAR: urgent
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_diagnostics_loads_external_rule_file(self) -> None:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cfg_rules_file_")
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        rules = root / "project_rules.yml"
        rules.write_text(
            """\
rules:
  - rule_id: REQUIRE_LIMIT
    message: add limit for list queries
    default_severity: warn
    match:
      statement_type_is: SELECT
      sql_contains: from users
    action:
      suggestion_sql_template: SELECT id FROM users LIMIT 100
      block_actionability: true
""",
            encoding="utf-8",
        )
        cfg = root / "sqlopt.yml"
        cfg.write_text(
            BASE_YAML
            + """\
diagnostics:
  rulepacks:
    - file: project_rules.yml
""",
            encoding="utf-8",
        )
        loaded = load_config(cfg)
        self.assertEqual(loaded["diagnostics"]["rulepacks"], [{"file": str(rules.resolve())}])
        self.assertEqual(loaded["diagnostics"]["loaded_rulepacks"][0]["rules"][0]["rule_id"], "REQUIRE_LIMIT")
        self.assertTrue(loaded["diagnostics"]["loaded_rulepacks"][0]["rules"][0]["action"]["block_actionability"])

    def test_diagnostics_rejects_invalid_external_rule_file(self) -> None:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cfg_rules_bad_")
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        rules = root / "project_rules.yml"
        rules.write_text(
            """\
rules:
  - rule_id: bad_name
    message: invalid
    match:
      sql_contains: select
""",
            encoding="utf-8",
        )
        cfg = root / "sqlopt.yml"
        cfg.write_text(
            BASE_YAML
            + """\
diagnostics:
  rulepacks:
    - file: project_rules.yml
""",
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)

    def test_validate_strategy_defaults_are_loaded(self) -> None:
        loaded = load_config(self._write_cfg(""))
        self.assertEqual(loaded["validate"]["selection_mode"], "patchability_first")
        self.assertTrue(loaded["validate"]["require_semantic_match"])
        self.assertFalse(loaded["validate"]["require_perf_evidence_for_pass"])
        self.assertFalse(loaded["validate"]["require_verified_evidence_for_pass"])
        self.assertEqual(loaded["validate"]["delivery_bias"], "conservative")

    def test_mysql_platform_is_accepted(self) -> None:
        td = tempfile.TemporaryDirectory(prefix="sqlopt_cfg_mysql_")
        self.addCleanup(td.cleanup)
        cfg = Path(td.name) / "sqlopt.yml"
        cfg.write_text(BASE_YAML.replace("platform: postgresql", "platform: mysql"), encoding="utf-8")
        loaded = load_config(cfg)
        self.assertEqual(loaded["db"]["platform"], "mysql")

    def test_validate_strategy_rejects_invalid_values(self) -> None:
        cfg = self._write_cfg(
            """\
validate:
  selection_mode: perf_first
"""
        )
        with self.assertRaises(ConfigError):
            load_config(cfg)


if __name__ == "__main__":
    unittest.main()
