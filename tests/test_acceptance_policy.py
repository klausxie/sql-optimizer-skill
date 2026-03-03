from __future__ import annotations

import unittest

from sqlopt.platforms.sql.acceptance_policy import build_acceptance_decision
from sqlopt.platforms.sql.models import EquivalenceCheck, PerfComparison


class AcceptancePolicyTest(unittest.TestCase):
    def test_semantic_mismatch_is_fail(self) -> None:
        decision = build_acceptance_decision(
            EquivalenceCheck(checked=True, method="static", row_count={"status": "MISMATCH"}, evidence_refs=[]),
            PerfComparison(
                checked=True,
                method="heuristic",
                before_summary={},
                after_summary={},
                reason_codes=[],
                improved=False,
                evidence_refs=[],
            ),
            "balanced",
            0,
        )

        self.assertEqual(decision.status, "FAIL")
        self.assertEqual(decision.feedback["reason_code"], "VALIDATE_EQUIVALENCE_MISMATCH")
        self.assertIn("VALIDATE_EQUIVALENCE_MISMATCH", decision.reason_codes)

    def test_balanced_semantic_match_without_improvement_is_pass_with_warning(self) -> None:
        decision = build_acceptance_decision(
            EquivalenceCheck(checked=True, method="static", row_count={"status": "MATCH"}, evidence_refs=[]),
            PerfComparison(
                checked=True,
                method="heuristic",
                before_summary={},
                after_summary={},
                reason_codes=[],
                improved=False,
                evidence_refs=[],
            ),
            "balanced",
            1,
        )

        self.assertEqual(decision.status, "PASS")
        self.assertIn("VALIDATE_PERF_NOT_IMPROVED_WARN", decision.warnings)
        self.assertIn("VALIDATE_PLACEHOLDER_SEMANTICS_MISMATCH_WARN", decision.warnings)


if __name__ == "__main__":
    unittest.main()
