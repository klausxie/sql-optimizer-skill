from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.devtools.harness.assertions import assert_validate_matrix_matches_scenarios
from sqlopt.devtools.harness.runtime import run_fixture_validate_harness


class HarnessValidateAssertionsTest(unittest.TestCase):
    def test_validate_assertions_accept_current_fixture_validate_harness(self) -> None:
        scenarios, _proposals, _acceptance_rows, _units_by_key, acceptance_by_key, _fragment_catalog = (
            run_fixture_validate_harness()
        )
        assert_validate_matrix_matches_scenarios(scenarios, acceptance_by_key)

    def test_validate_assertions_apply_fixture_rewrite_expectations(self) -> None:
        scenarios = [
            {
                "sqlKey": "demo.user.advanced.listUsersFilteredAliased",
                "targetValidateStatus": "PASS",
                "targetSemanticGate": "PASS",
            }
        ]
        acceptance_by_key = {
            "demo.user.advanced.listUsersFilteredAliased": {
                "status": "PASS",
                "semanticEquivalence": {"status": "PASS"},
                "rewriteFacts": {
                    "dynamicTemplate": {
                        "present": True,
                        "capabilityProfile": {
                            "shapeFamily": "IF_GUARDED_FILTER_STATEMENT",
                            "capabilityTier": "SAFE_BASELINE",
                            "patchSurface": "STATEMENT_BODY",
                            "baselineFamily": "WRONG_BASELINE",
                        },
                    }
                },
            }
        }

        with self.assertRaisesRegex(AssertionError, "baselineFamily"):
            assert_validate_matrix_matches_scenarios(scenarios, acceptance_by_key)


if __name__ == "__main__":
    unittest.main()
