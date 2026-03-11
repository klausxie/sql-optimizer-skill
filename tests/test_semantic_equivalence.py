from __future__ import annotations

import unittest

from sqlopt.platforms.sql.semantic_equivalence import build_semantic_equivalence


class SemanticEquivalenceTest(unittest.TestCase):
    def test_pass_when_row_count_matches_and_core_clauses_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users WHERE status = 1 ORDER BY created_at DESC LIMIT 10",
            rewritten_sql="SELECT id FROM users WHERE status = 1 ORDER BY created_at DESC LIMIT 10",
            equivalence={"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []},
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["confidence"], "MEDIUM")
        self.assertEqual(result["evidenceLevel"], "DB_COUNT")
        self.assertEqual(result["checks"]["predicate"]["status"], "PASS")
        self.assertEqual(result["checks"]["ordering"]["status"], "PASS")
        self.assertEqual(result["checks"]["pagination"]["status"], "PASS")

    def test_fail_when_where_clause_is_added_or_removed(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users WHERE status = 1",
            rewritten_sql="SELECT id FROM users",
            equivalence={"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []},
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["confidence"], "HIGH")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_ADDED_OR_REMOVED")
        self.assertIn("SEMANTIC_PREDICATE_ADDED_OR_REMOVED", result["hardConflicts"])

    def test_uncertain_when_row_count_not_verified(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users",
            rewritten_sql="SELECT id FROM users",
            equivalence={"checked": False, "method": "capability_gate", "rowCount": {"status": "SKIPPED"}, "evidenceRefs": []},
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(result["confidence"], "LOW")
        self.assertEqual(result["evidenceLevel"], "STRUCTURE")
        self.assertIn("SEMANTIC_ROW_COUNT_UNVERIFIED", result["reasons"])

    def test_uncertain_when_projection_changes(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id, name FROM users",
            equivalence={"checked": True, "method": "sql_semantic_compare_v1", "rowCount": {"status": "MATCH"}, "evidenceRefs": []},
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(result["confidence"], "MEDIUM")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_CHANGED")

    def test_high_confidence_when_fingerprint_matches(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users WHERE status = 1",
            rewritten_sql="SELECT id FROM users WHERE status = 1",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["confidence"], "HIGH")
        self.assertEqual(result["confidenceBeforeUpgrade"], "MEDIUM")
        self.assertTrue(result["confidenceUpgradeApplied"])
        self.assertIn("SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_EXACT", result["confidenceUpgradeReasons"])
        self.assertEqual(result["confidenceUpgradeEvidenceSources"], ["DB_FINGERPRINT"])
        self.assertEqual(result["evidenceLevel"], "DB_FINGERPRINT")

    def test_partial_fingerprint_can_raise_low_confidence_to_medium(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users",
            rewritten_sql="SELECT id FROM users",
            equivalence={
                "checked": False,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "SKIPPED"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [
                    {
                        "source": "DB_FINGERPRINT",
                        "fingerprint_key": "row_sample_hash",
                        "match_strength": "PARTIAL",
                    }
                ],
            },
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(result["confidenceBeforeUpgrade"], "LOW")
        self.assertEqual(result["confidence"], "MEDIUM")
        self.assertTrue(result["confidenceUpgradeApplied"])

    def test_sample_mismatch_does_not_create_hard_conflict(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id FROM users",
            rewritten_sql="SELECT id FROM users",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "rowSampleHash": {"status": "MISMATCH"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertIn("SEMANTIC_FINGERPRINT_SAMPLE_MISMATCH", result["reasons"])
        self.assertNotIn("SEMANTIC_FINGERPRINT_SAMPLE_MISMATCH", result["hardConflicts"])

    def test_count_projection_known_equivalence_can_override_uncertain_to_pass(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT COUNT(1) FROM users",
            rewritten_sql="SELECT COUNT(*) FROM users",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "keySetHash": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_COUNT_STAR_ONE")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_COUNT_EQUIVALENT")
        self.assertIn("SEMANTIC_KNOWN_EQUIVALENCE_COUNT_STAR_ONE", result["reasons"])
        self.assertEqual(result["confidence"], "HIGH")

    def test_count_projection_override_requires_exact_fingerprint_strength(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT COUNT(1) FROM users",
            rewritten_sql="SELECT COUNT(*) FROM users",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v2",
                "rowCount": {"status": "MATCH"},
                "rowSampleHash": {"status": "MATCH"},
                "evidenceRefs": [],
                "evidenceRefObjects": [
                    {
                        "source": "DB_FINGERPRINT",
                        "fingerprint_key": "row_sample_hash",
                        "match_strength": "PARTIAL",
                    }
                ],
            },
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertFalse(result["equivalenceOverrideApplied"])
        self.assertIsNone(result["equivalenceOverrideRule"])
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_CHANGED")


if __name__ == "__main__":
    unittest.main()
