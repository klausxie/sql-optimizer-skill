from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.platforms.sql.canonicalization import assess_candidate_canonicalization
from sqlopt.platforms.sql.canonicalization_engine import assess_candidate_canonicalization_model
from sqlopt.platforms.sql.canonicalization_models import CanonicalMatch, RegisteredCanonicalRule


class CanonicalizationTest(unittest.TestCase):
    def test_prefers_count_star_for_exact_count_candidate(self) -> None:
        result = assess_candidate_canonicalization(
            "select count(1) from (select id from users) tmp",
            "SELECT COUNT(*) FROM users",
            {
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            },
        )
        self.assertTrue(result["preferred"])
        self.assertEqual(result["ruleId"], "COUNT_CANONICAL_FORM")
        self.assertGreater(result["score"], 0)

    def test_detects_alias_only_canonical_form(self) -> None:
        result = assess_candidate_canonicalization(
            "SELECT id AS user_id, name AS user_name FROM users",
            "SELECT id, name FROM users",
            {
                "rowCount": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
            },
        )
        self.assertTrue(result["preferred"])
        self.assertIn(
            "ALIAS_ONLY_CANONICAL_FORM",
            {row["ruleId"] for row in result["matchedRules"]},
        )

    def test_detects_redundant_subquery_wrapper(self) -> None:
        result = assess_candidate_canonicalization(
            "SELECT id, name FROM (SELECT id, name FROM users) u",
            "SELECT id, name FROM users",
            {
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
            },
        )
        self.assertTrue(result["preferred"])
        self.assertIn(
            "REDUNDANT_SUBQUERY_CANONICAL_FORM",
            {row["ruleId"] for row in result["matchedRules"]},
        )

    def test_blocks_canonicalization_without_row_count_match(self) -> None:
        result = assess_candidate_canonicalization(
            "SELECT id AS user_id FROM users",
            "SELECT id FROM users",
            {
                "rowCount": {"status": "SKIPPED"},
            },
        )
        self.assertFalse(result["preferred"])
        self.assertEqual(result["score"], 0)

    def test_engine_uses_rule_priority_for_primary_match(self) -> None:
        class LowerPriorityRule:
            def evaluate(self, _context):
                return CanonicalMatch(
                    rule_id="LOWER_PRIORITY_HIGHER_SCORE",
                    preferred_direction="TEST",
                    score_delta=20,
                    reason="lower priority but higher score",
                )

        class HigherPriorityRule:
            def evaluate(self, _context):
                return CanonicalMatch(
                    rule_id="HIGHER_PRIORITY_LOWER_SCORE",
                    preferred_direction="TEST",
                    score_delta=5,
                    reason="higher priority wins primary selection",
                )

        with patch(
            "sqlopt.platforms.sql.canonicalization_engine.iter_canonical_rules",
            return_value=(
                RegisteredCanonicalRule(
                    rule_id="LOWER_PRIORITY_HIGHER_SCORE",
                    priority=100,
                    implementation=LowerPriorityRule(),
                ),
                RegisteredCanonicalRule(
                    rule_id="HIGHER_PRIORITY_LOWER_SCORE",
                    priority=200,
                    implementation=HigherPriorityRule(),
                ),
            ),
        ):
            result = assess_candidate_canonicalization_model(
                "SELECT id FROM users",
                "SELECT id FROM users",
                {"rowCount": {"status": "MATCH"}},
            )

        self.assertEqual(result.preference.primary_rule, "HIGHER_PRIORITY_LOWER_SCORE")
        self.assertEqual(result.preference.reason, "higher priority wins primary selection")


if __name__ == "__main__":
    unittest.main()
