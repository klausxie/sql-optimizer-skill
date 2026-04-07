from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.devtools.harness.assertions import (
    assert_if_guarded_statement_convergence,
    assert_validate_matrix_matches_scenarios,
)
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

    def test_if_guarded_statement_convergence_accepts_auto_patchable_consensus(self) -> None:
        acceptance_by_key = {
            "demo.user.advanced.listUsersFilteredAliased": {
                "sqlKey": "demo.user.advanced.listUsersFilteredAliased",
                "statementKey": "demo.user.advanced.listUsersFilteredAliased",
                "rewriteFacts": {
                    "dynamicTemplate": {
                        "capabilityProfile": {"shapeFamily": "IF_GUARDED_FILTER_STATEMENT"}
                    }
                },
            }
        }
        convergence_rows = [
            {
                "statementKey": "demo.user.advanced.listUsersFilteredAliased",
                "convergenceDecision": "AUTO_PATCHABLE",
                "consensus": {"patchFamily": "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"},
                "conflictReason": None,
            }
        ]

        assert_if_guarded_statement_convergence(convergence_rows, acceptance_by_key)

    def test_if_guarded_statement_convergence_requires_conflict_reason_when_blocked(self) -> None:
        acceptance_by_key = {
            "demo.user.advanced.listUsersFilteredAliased": {
                "sqlKey": "demo.user.advanced.listUsersFilteredAliased",
                "statementKey": "demo.user.advanced.listUsersFilteredAliased",
                "rewriteFacts": {
                    "dynamicTemplate": {
                        "capabilityProfile": {"shapeFamily": "IF_GUARDED_FILTER_STATEMENT"}
                    }
                },
            }
        }
        convergence_rows = [
            {
                "statementKey": "demo.user.advanced.listUsersFilteredAliased",
                "convergenceDecision": "MANUAL_REVIEW",
                "consensus": None,
                "conflictReason": None,
            }
        ]

        with self.assertRaisesRegex(AssertionError, "conflictReason"):
            assert_if_guarded_statement_convergence(convergence_rows, acceptance_by_key)


if __name__ == "__main__":
    unittest.main()
