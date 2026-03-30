from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.acceptance_policy import build_acceptance_decision
from sqlopt.platforms.sql.candidate_selection import (
    build_candidate_pool,
    evaluate_candidate_selection,
    filter_valid_candidates,
)
from sqlopt.platforms.sql.candidate_patchability import assess_candidate_patchability_model
from sqlopt.platforms.sql.models import Candidate, EquivalenceCheck, PerfComparison


class CandidateSelectionModuleTest(unittest.TestCase):
    def test_build_candidate_pool_deduplicates_sql_across_sources(self) -> None:
        proposal = {
            "llmCandidates": [
                {"id": "c1", "rewrittenSql": "SELECT id FROM users"},
                {"id": "c2", "rewrittenSql": "SELECT id FROM users"},
            ],
            "suggestions": [{"action": "RULE", "sql": "SELECT id FROM users"}],
        }

        candidates = build_candidate_pool("demo.user.listUsers#v1", proposal)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].id, "c1")

    def test_evaluate_candidate_selection_chooses_best_improved_candidate(self) -> None:
        valid_candidates = [
            Candidate(id="c1", source="llm", rewritten_sql="SELECT id FROM users", rewrite_strategy="llm"),
            Candidate(
                id="c2",
                source="llm",
                rewritten_sql="SELECT id FROM users ORDER BY created_at DESC",
                rewrite_strategy="llm",
            ),
        ]

        def fake_semantics(_policy, _cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_policy, _cfg, _orig, rewritten, _dir):
            if rewritten == "SELECT id FROM users":
                return {
                    "checked": True,
                    "method": "sql_explain_json_compare",
                    "beforeSummary": {"totalCost": 10.0},
                    "afterSummary": {"totalCost": 9.0},
                    "reasonCodes": ["TOTAL_COST_REDUCED"],
                    "improved": True,
                    "evidenceRefs": [],
                }
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="candidate_selection_") as td:
            result = evaluate_candidate_selection(
                "SELECT * FROM users",
                {"suggestions": []},
                {"db": {"dsn": "postgresql://dummy"}},
                Path(td),
                object(),
                valid_candidates,
                fake_semantics,
                fake_plan,
                compare_enabled=True,
            )

        self.assertEqual(result.rewritten_sql, "SELECT id FROM users ORDER BY created_at DESC")
        self.assertEqual(result.selected_candidate_id, "c2")
        self.assertEqual(result.selected_candidate_source, "llm")
        self.assertEqual(len(result.candidate_evaluations), 2)

    def test_filter_valid_candidates_rejects_question_mark_rewrite_for_hash_placeholders(self) -> None:
        candidates = [
            Candidate(
                id="c1",
                source="llm",
                rewritten_sql="SELECT * FROM users WHERE status = ?",
                rewrite_strategy="test",
            )
        ]

        valid, rejected = filter_valid_candidates("SELECT * FROM users WHERE status = #{status}", candidates)

        self.assertEqual(valid, [])
        self.assertEqual(rejected, 1)

    def test_filter_valid_candidates_rejects_natural_language_fallback(self) -> None:
        candidates = [
            Candidate(
                id="fallback:text",
                source="llm",
                rewritten_sql="The main optimization is removing the unnecessary subquery wrapper.",
                rewrite_strategy="opencode_text_fallback",
            )
        ]

        valid, rejected = filter_valid_candidates("select count(1) from users", candidates)

        self.assertEqual(valid, [])
        self.assertEqual(rejected, 0)

    def test_evaluate_candidate_selection_prefers_effective_change_over_noop(self) -> None:
        valid_candidates = [
            Candidate(id="c1", source="llm", rewritten_sql="SELECT * FROM users", rewrite_strategy="llm"),
            Candidate(id="c2", source="llm", rewritten_sql="SELECT id FROM users", rewrite_strategy="projection"),
        ]

        def fake_semantics(_policy, _cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_policy, _cfg, _orig, _rewritten, _dir):
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 9.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="candidate_selection_noop_") as td:
            result = evaluate_candidate_selection(
                "SELECT * FROM users",
                {"suggestions": []},
                {"db": {"dsn": "postgresql://dummy"}},
                Path(td),
                object(),
                valid_candidates,
                fake_semantics,
                fake_plan,
                compare_enabled=True,
            )

        self.assertEqual(result.selected_candidate_id, "c2")
        self.assertEqual(result.rewritten_sql, "SELECT id FROM users")

    def test_typed_selection_objects_still_render_contract_payloads(self) -> None:
        decision = build_acceptance_decision(
            EquivalenceCheck(checked=True, method="static", row_count={"status": "MATCH"}, evidence_refs=[]),
            PerfComparison(
                checked=True,
                method="heuristic",
                before_summary={},
                after_summary={"totalCost": 9},
                reason_codes=[],
                improved=False,
                evidence_refs=[],
            ),
            "balanced",
            0,
        )

        self.assertEqual(decision.status, "PASS")

    def test_candidate_patchability_evaluator_stays_compatible_with_selection_scores(self) -> None:
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
        self.assertIn("projection-style rewrite is easy to patch", assessment.reasons)

    def test_prefers_structural_groupby_flatten_over_speculative_limit_candidate(self) -> None:
        original_sql = (
            "SELECT status, COUNT(*) AS total FROM "
            "(SELECT status, COUNT(*) AS total FROM orders GROUP BY status) og ORDER BY status"
        )
        valid_candidates = [
            Candidate(
                id="c1",
                source="llm",
                rewritten_sql="SELECT status, COUNT(*) AS total FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY status LIMIT 100",
                rewrite_strategy="ADD_TIME_FILTER",
            ),
            Candidate(
                id="c2",
                source="llm",
                rewritten_sql="SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY status",
                rewrite_strategy="REMOVE_REDUNDANT_GROUP_BY_WRAPPER_RECOVERED",
            ),
        ]

        def fake_semantics(_policy, _cfg, _orig, _rewritten, _dir):
            return {"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []}

        def fake_plan(_policy, _cfg, _orig, rewritten, _dir):
            improved = "LIMIT 100" not in rewritten
            return {
                "checked": True,
                "method": "sql_explain_json_compare",
                "beforeSummary": {"totalCost": 10.0},
                "afterSummary": {"totalCost": 9.0 if improved else 8.0},
                "reasonCodes": ["TOTAL_COST_REDUCED"],
                "improved": True,
                "evidenceRefs": [],
            }

        with tempfile.TemporaryDirectory(prefix="candidate_selection_groupby_") as td:
            result = evaluate_candidate_selection(
                original_sql,
                {"suggestions": []},
                {"db": {"dsn": "postgresql://dummy"}},
                Path(td),
                object(),
                valid_candidates,
                fake_semantics,
                fake_plan,
                compare_enabled=True,
            )

        self.assertEqual(result.selected_candidate_id, "c2")
        self.assertEqual(result.rewritten_sql, valid_candidates[1].rewritten_sql)


if __name__ == "__main__":
    unittest.main()
