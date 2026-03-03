from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.platforms.base import PlatformCapabilities
from sqlopt.stages.preflight_strategy import build_preflight_policy


class PreflightStrategyTest(unittest.TestCase):
    def test_db_policy_skips_when_db_reachable_disabled(self) -> None:
        policy = build_preflight_policy({"validate": {"db_reachable": False}})

        self.assertFalse(policy.db.enabled)
        self.assertEqual(policy.db.reason, "validate.db_reachable=false")

    def test_db_policy_skips_when_platform_disables_connectivity(self) -> None:
        with patch(
            "sqlopt.stages.preflight_strategy.get_platform_capabilities",
            return_value=PlatformCapabilities(
                supports_connectivity_check=False,
                supports_plan_compare=True,
                supports_semantic_compare=True,
                supports_sql_evidence=True,
            ),
        ):
            policy = build_preflight_policy(
                {"db": {"platform": "postgresql"}, "validate": {"db_reachable": True}}
            )

        self.assertFalse(policy.db.enabled)
        self.assertEqual(policy.db.reason, "platform capability disables connectivity check")

    def test_db_policy_enables_mysql_connectivity_when_supported(self) -> None:
        policy = build_preflight_policy({"db": {"platform": "mysql"}, "validate": {"db_reachable": True}})

        self.assertTrue(policy.db.enabled)
        self.assertIsNone(policy.db.reason)

    def test_llm_policy_selects_provider_mode(self) -> None:
        direct = build_preflight_policy({"llm": {"enabled": True, "provider": "direct_openai_compatible"}})
        opencode = build_preflight_policy({"llm": {"enabled": True, "provider": "opencode_run"}})
        builtin = build_preflight_policy({"llm": {"enabled": True, "provider": "opencode_builtin"}})

        self.assertEqual(direct.llm.mode, "direct_openai_compatible")
        self.assertTrue(direct.llm.enabled)
        self.assertEqual(opencode.llm.mode, "opencode_run")
        self.assertTrue(opencode.llm.enabled)
        self.assertEqual(builtin.llm.mode, "disabled")
        self.assertFalse(builtin.llm.enabled)
        self.assertEqual(builtin.llm.reason, "provider=opencode_builtin")

    def test_scanner_policy_skips_when_jar_not_set(self) -> None:
        policy = build_preflight_policy({"scan": {}})

        self.assertFalse(policy.scanner.enabled)
        self.assertEqual(policy.scanner.reason, "scan.java_scanner.jar_path not set")


if __name__ == "__main__":
    unittest.main()
