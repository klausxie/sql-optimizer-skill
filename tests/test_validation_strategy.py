from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.platforms.base import PlatformCapabilities
from sqlopt.platforms.sql import validation_strategy


class ValidationStrategyTest(unittest.TestCase):
    def test_build_compare_policy_uses_default_capabilities_when_platform_missing(self) -> None:
        policy = validation_strategy.build_compare_policy({"db": {"dsn": "postgresql://dummy"}, "validate": {}})

        self.assertTrue(policy.semantics_enabled)
        self.assertTrue(policy.plan_enabled)
        self.assertIsNone(policy.semantics_skip_reason)
        self.assertIsNone(policy.plan_skip_reason)

    def test_build_compare_policy_respects_capability_and_config_gates(self) -> None:
        with patch(
            "sqlopt.platforms.sql.validation_strategy.get_platform_capabilities",
            return_value=PlatformCapabilities(
                supports_connectivity_check=True,
                supports_plan_compare=False,
                supports_semantic_compare=False,
                supports_sql_evidence=True,
            ),
        ):
            policy = validation_strategy.build_compare_policy(
                {"db": {"platform": "postgresql"}, "validate": {"plan_compare_enabled": False}}
            )

        self.assertFalse(policy.semantics_enabled)
        self.assertFalse(policy.plan_enabled)
        self.assertEqual(policy.semantics_skip_reason, "VALIDATE_SEMANTIC_COMPARE_DISABLED")
        self.assertEqual(policy.plan_skip_reason, "VALIDATE_PLAN_COMPARE_DISABLED")

    def test_run_compare_helpers_skip_without_calling_runner(self) -> None:
        policy = validation_strategy.ValidationComparePolicy(
            capabilities=PlatformCapabilities(),
            semantics_enabled=False,
            plan_enabled=False,
            semantics_skip_reason="VALIDATE_SEMANTIC_COMPARE_DISABLED",
            plan_skip_reason="VALIDATE_PLAN_COMPARE_CONFIG_DISABLED",
        )
        runner = Mock()

        with tempfile.TemporaryDirectory(prefix="sqlopt_validation_strategy_") as td:
            evidence_dir = Path(td)
            semantics = validation_strategy.run_semantics_compare(policy, runner, {}, "SELECT 1", "SELECT 1", evidence_dir)
            plan = validation_strategy.run_plan_compare(policy, runner, {}, "SELECT 1", "SELECT 1", evidence_dir)

        runner.assert_not_called()
        self.assertFalse(semantics["checked"])
        self.assertEqual(semantics["reasonCodes"], ["VALIDATE_SEMANTIC_COMPARE_DISABLED"])
        self.assertFalse(plan["checked"])
        self.assertEqual(plan["reasonCodes"], ["VALIDATE_PLAN_COMPARE_CONFIG_DISABLED"])


if __name__ == "__main__":
    unittest.main()
