from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.platforms.sql.candidate_selection import (
    build_candidate_pool,
    evaluate_candidate_selection,
    filter_valid_candidates,
)


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
        self.assertEqual(candidates[0]["id"], "c1")

    def test_evaluate_candidate_selection_chooses_best_improved_candidate(self) -> None:
        valid_candidates = [
            {"id": "c1", "source": "llm", "rewrittenSql": "SELECT id FROM users"},
            {"id": "c2", "source": "llm", "rewrittenSql": "SELECT id FROM users ORDER BY created_at DESC"},
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
        candidates = [{"id": "c1", "source": "llm", "rewrittenSql": "SELECT * FROM users WHERE status = ?"}]

        valid, rejected = filter_valid_candidates("SELECT * FROM users WHERE status = #{status}", candidates)

        self.assertEqual(valid, [])
        self.assertEqual(rejected, 1)


if __name__ == "__main__":
    unittest.main()
