from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.platforms import dispatch
from sqlopt.platforms.base import FunctionPlatformAdapter, PlatformCapabilities
from sqlopt.platforms.sql.validation_strategy import build_compare_policy
from sqlopt.stages.preflight_strategy import build_preflight_policy


class _LegacyFakePlatform:
    def check_db_connectivity(self, config: dict) -> dict:
        return {"name": "db", "enabled": True, "ok": True, "platform": config["db"]["platform"]}

    def collect_sql_evidence(self, config: dict, sql: str) -> tuple[dict, dict]:
        return {"platform": config["db"]["platform"]}, {"sql": sql}

    def compare_plan(self, config: dict, original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict:
        return {"checked": True, "improved": True, "platform": config["db"]["platform"]}

    def compare_semantics(self, config: dict, original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict:
        return {"checked": True, "rowCount": {"status": "MATCH"}, "platform": config["db"]["platform"]}


class PlatformAdapterCompatTest(unittest.TestCase):
    def test_dispatch_wraps_legacy_module_like_entry(self) -> None:
        cfg = {"db": {"platform": "fake"}}
        with patch("sqlopt.platforms.dispatch._registry", return_value={"fake": _LegacyFakePlatform()}):
            adapter = dispatch.get_platform_adapter(cfg)
            capabilities = dispatch.get_platform_capabilities(cfg)
            evidence, payload = dispatch.collect_sql_evidence(cfg, "SELECT 1")

        self.assertEqual(adapter.name, "fake")
        self.assertIsInstance(adapter, FunctionPlatformAdapter)
        self.assertTrue(capabilities.supports_plan_compare)
        self.assertEqual(evidence["platform"], "fake")
        self.assertEqual(payload["sql"], "SELECT 1")

    def test_strategy_layers_consume_fake_adapter_capabilities(self) -> None:
        fake_adapter = FunctionPlatformAdapter(
            name="fake",
            capabilities=PlatformCapabilities(
                supports_connectivity_check=False,
                supports_plan_compare=False,
                supports_semantic_compare=True,
                supports_sql_evidence=True,
            ),
            check_db_connectivity_fn=lambda config: {"ok": True},
            collect_sql_evidence_fn=lambda config, sql: ({}, {}),
            compare_plan_fn=lambda config, original_sql, rewritten_sql, evidence_dir: {"checked": True},
            compare_semantics_fn=lambda config, original_sql, rewritten_sql, evidence_dir: {"checked": True},
        )
        cfg = {"db": {"platform": "fake"}, "validate": {"db_reachable": True, "plan_compare_enabled": True}}

        with patch("sqlopt.platforms.dispatch._registry", return_value={"fake": fake_adapter}):
            preflight_policy = build_preflight_policy(cfg)
            compare_policy = build_compare_policy(cfg)

        self.assertFalse(preflight_policy.db.enabled)
        self.assertEqual(preflight_policy.db.reason, "platform capability disables connectivity check")
        self.assertTrue(compare_policy.semantics_enabled)
        self.assertFalse(compare_policy.plan_enabled)
        self.assertEqual(compare_policy.plan_skip_reason, "VALIDATE_PLAN_COMPARE_DISABLED")

    def test_dispatch_rejects_invalid_registry_entry(self) -> None:
        cfg = {"db": {"platform": "broken"}}
        with patch("sqlopt.platforms.dispatch._registry", return_value={"broken": object()}):
            with self.assertRaises(Exception) as cm:
                dispatch.get_platform_adapter(cfg)

        self.assertEqual(getattr(cm.exception, "reason_code", None), "INVALID_PLATFORM_ADAPTER")


if __name__ == "__main__":
    unittest.main()
