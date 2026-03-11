from __future__ import annotations

import unittest

from sqlopt.platforms.sql.candidate_models import Candidate
from sqlopt.platforms.sql.candidate_patchability import assess_candidate_patchability_model


class CandidatePatchabilityTest(unittest.TestCase):
    def test_rule_projection_candidate_gets_expected_score(self) -> None:
        assessment = assess_candidate_patchability_model(
            "SELECT * FROM users",
            Candidate(
                id="c1",
                source="rule",
                rewritten_sql="SELECT id FROM users",
                rewrite_strategy="PROJECT_COLUMNS",
            ),
        )

        self.assertEqual(assessment.score, 90)
        self.assertEqual(assessment.tier, "HIGH")
        self.assertEqual(
            [row.rule_id for row in assessment.matched_rules],
            ["RULE_SOURCE_CONSERVATIVE", "PROJECTION_REWRITE_PATCHABLE"],
        )

    def test_join_and_generic_placeholder_reduce_patchability(self) -> None:
        assessment = assess_candidate_patchability_model(
            "SELECT id FROM users WHERE status = #{status}",
            Candidate(
                id="c2",
                source="llm",
                rewritten_sql="SELECT u.id FROM users u JOIN orders o ON o.user_id = u.id WHERE u.status = ?",
                rewrite_strategy="llm",
            ),
        )

        self.assertEqual(assessment.score, 30)
        self.assertEqual(assessment.tier, "LOW")
        self.assertEqual(
            {row.rule_id for row in assessment.matched_rules},
            {"JOIN_HEAVY_PATCH_SURFACE", "GENERIC_PLACEHOLDER_PENALTY"},
        )


if __name__ == "__main__":
    unittest.main()
