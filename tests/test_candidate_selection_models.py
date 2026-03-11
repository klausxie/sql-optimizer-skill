from __future__ import annotations

import unittest

from sqlopt.platforms.sql.candidate_selection_models import (
    CandidateCanonicalizationAssessmentEntry,
    CandidateSelectionRank,
    CandidateSelectionTraceEntry,
)


class CandidateSelectionModelsTest(unittest.TestCase):
    def test_rank_tuple_prefers_effective_change_before_other_signals(self) -> None:
        noop_rank = CandidateSelectionRank(
            effective_change=False,
            patchability_score=100,
            canonical_score=100,
            improved=True,
            after_cost=1.0,
        )
        effective_rank = CandidateSelectionRank(
            effective_change=True,
            patchability_score=60,
            canonical_score=0,
            improved=False,
            after_cost=10.0,
        )

        self.assertGreater(effective_rank.as_tuple(), noop_rank.as_tuple())

    def test_trace_and_assessment_entries_render_contract_shape(self) -> None:
        rank = CandidateSelectionRank(
            effective_change=True,
            patchability_score=60,
            canonical_score=33,
            improved=False,
            after_cost=10.0,
        )
        trace = CandidateSelectionTraceEntry(
            candidate_id="c1",
            semantic_match=True,
            effective_change=True,
            patchability_score=60,
            canonical_score=33,
            improved=False,
            after_cost=10.0,
            rank=rank,
        ).to_dict()
        assessment = CandidateCanonicalizationAssessmentEntry(
            candidate_id="c1",
            source="llm",
            rewritten_sql="SELECT COUNT(*) FROM users",
            preferred=True,
            rule_id="COUNT_CANONICAL_FORM",
            score=33,
            reason="count(*) is preferred as canonical count form",
            matched_rules=[{"ruleId": "COUNT_CANONICAL_FORM"}],
        ).to_dict()

        self.assertEqual(trace["rank"], [1, 60, 33, 0, -10.0])
        self.assertEqual(assessment["candidateId"], "c1")
        self.assertEqual(assessment["ruleId"], "COUNT_CANONICAL_FORM")

    def test_trace_rank_avoids_infinity_for_missing_cost(self) -> None:
        rank = CandidateSelectionRank(
            effective_change=True,
            patchability_score=60,
            canonical_score=33,
            improved=False,
            after_cost=float("inf"),
        )

        trace = CandidateSelectionTraceEntry(
            candidate_id="c1",
            semantic_match=True,
            effective_change=True,
            patchability_score=60,
            canonical_score=33,
            improved=False,
            after_cost=None,
            rank=rank,
        ).to_dict()

        self.assertEqual(trace["rank"], [1, 60, 33, 0, None])


if __name__ == "__main__":
    unittest.main()
