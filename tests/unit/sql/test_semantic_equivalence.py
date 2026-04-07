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

    def test_simple_cte_inline_is_treated_as_semantically_equivalent_with_exact_evidence(self) -> None:
        result = build_semantic_equivalence(
            original_sql="""
                WITH recent_users AS (
                    SELECT id, name, email, status, created_at, updated_at
                    FROM users
                    WHERE created_at >= #{createdAfter}
                )
                SELECT id, name, email, status, created_at, updated_at
                FROM recent_users
                ORDER BY created_at DESC
                LIMIT 20
            """,
            rewritten_sql="""
                SELECT id, name, email, status, created_at, updated_at
                FROM users
                WHERE created_at >= #{createdAfter}
                ORDER BY created_at DESC
                LIMIT 20
            """,
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
        self.assertEqual(result["checks"]["projection"]["status"], "PASS")
        self.assertEqual(result["checks"]["predicate"]["status"], "PASS")
        self.assertEqual(result["checks"]["ordering"]["status"], "PASS")
        self.assertEqual(result["checks"]["pagination"]["status"], "PASS")
        self.assertEqual(result["confidence"], "HIGH")

    def test_simple_count_wrapper_collapse_is_treated_as_semantically_equivalent(self) -> None:
        result = build_semantic_equivalence(
            original_sql="""
                SELECT COUNT(1)
                FROM (
                    SELECT id
                    FROM users
                    WHERE status = #{status}
                      AND created_at >= #{createdAfter}
                ) filtered_users
            """,
            rewritten_sql="""
                SELECT COUNT(*)
                FROM users
                WHERE status = #{status}
                  AND created_at >= #{createdAfter}
            """,
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

    def test_static_alias_projection_cleanup_is_treated_as_semantically_equivalent(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id AS id, name AS name, email AS email FROM users ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name, email FROM users ORDER BY created_at DESC",
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
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_ALIAS_ONLY_EQUIVALENT")
        self.assertEqual(result["confidence"], "HIGH")

    def test_projection_qualifier_only_cleanup_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT users.id AS id, users.name AS name, users.email AS email, users.status AS status, "
                "users.created_at AS created_at, users.updated_at AS updated_at "
                "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
            rewritten_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
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
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_QUALIFIER_ONLY_EQUIVALENT")
        self.assertEqual(result["confidence"], "HIGH")

    def test_ordering_qualifier_only_cleanup_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
            ),
            rewritten_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
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
        self.assertEqual(result["checks"]["ordering"]["reasonCode"], "SEMANTIC_ORDERING_QUALIFIER_ONLY_EQUIVALENT")
        self.assertEqual(result["confidence"], "HIGH")

    def test_predicate_and_ordering_qualifier_only_cleanup_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
            ),
            rewritten_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
            ),
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
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_QUALIFIER_ONLY_EQUIVALENT")
        self.assertEqual(result["checks"]["ordering"]["reasonCode"], "SEMANTIC_ORDERING_QUALIFIER_ONLY_EQUIVALENT")
        self.assertEqual(result["confidence"], "HIGH")

    def test_update_noop_is_treated_as_semantically_stable_even_without_row_count(self) -> None:
        result = build_semantic_equivalence(
            original_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            rewritten_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "update compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_DML_TARGET_STABLE")
        self.assertEqual(result["checks"]["dmlSet"]["reasonCode"], "SEMANTIC_DML_SET_STABLE")
        self.assertIn("SEMANTIC_DML_NOOP_STABLE", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_update_set_change_remains_uncertain(self) -> None:
        result = build_semantic_equivalence(
            original_sql="UPDATE users SET status = #{status} WHERE id = #{id}",
            rewritten_sql="UPDATE users SET status = COALESCE(#{status}, status) WHERE id = #{id}",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "SKIPPED"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(result["checks"]["dmlSet"]["reasonCode"], "SEMANTIC_DML_SET_CHANGED")

    def test_group_by_wrapper_safe_baseline_is_treated_as_semantically_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount "
                "FROM (SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status) og "
                "ORDER BY status"
            ),
            rewritten_sql="SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "aggregate compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_REDUNDANT_GROUP_BY_WRAPPER")
        self.assertIn("SEMANTIC_SAFE_BASELINE_REDUNDANT_GROUP_BY_WRAPPER", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_having_wrapper_safe_baseline_is_treated_as_semantically_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT user_id, COUNT(*) AS total "
                "FROM (SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1) oh "
                "ORDER BY user_id"
            ),
            rewritten_sql="SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "aggregate compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_REDUNDANT_HAVING_WRAPPER")
        self.assertIn("SEMANTIC_SAFE_BASELINE_REDUNDANT_HAVING_WRAPPER", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_group_by_from_alias_cleanup_is_treated_as_semantically_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount "
                "FROM orders o GROUP BY o.status ORDER BY o.status"
            ),
            rewritten_sql=(
                "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount "
                "FROM orders GROUP BY status ORDER BY status"
            ),
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "aggregate compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_GROUP_BY_FROM_ALIAS_CLEANUP")
        self.assertIn("SEMANTIC_SAFE_BASELINE_GROUP_BY_FROM_ALIAS_CLEANUP", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_group_by_having_from_alias_cleanup_is_treated_as_semantically_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT o.user_id AS user_id, COUNT(*) AS total "
                "FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id"
            ),
            rewritten_sql=(
                "SELECT user_id, COUNT(*) AS total "
                "FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id"
            ),
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "aggregate compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_GROUP_BY_HAVING_FROM_ALIAS_CLEANUP")
        self.assertIn("SEMANTIC_SAFE_BASELINE_GROUP_BY_HAVING_FROM_ALIAS_CLEANUP", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_boolean_tautology_removal_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users WHERE 1 = 1 ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_BOOLEAN_TAUTOLOGY_REMOVAL")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_BOOLEAN_TAUTOLOGY_EQUIVALENT")

    def test_single_value_in_list_simplification_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users WHERE status = 'ACTIVE' ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_SINGLE_VALUE_IN_LIST")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_SINGLE_VALUE_IN_LIST_EQUIVALENT")

    def test_constant_order_by_removal_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name, email FROM users ORDER BY NULL",
            rewritten_sql="SELECT id, name, email FROM users",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_CONSTANT_ORDER_BY_REMOVAL")
        self.assertEqual(result["checks"]["ordering"]["reasonCode"], "SEMANTIC_ORDERING_CONSTANT_ORDER_BY_EQUIVALENT")

    def test_constant_order_by_removal_safe_baseline_upgrades_confidence_without_db_rowcount_match(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name, email FROM users ORDER BY NULL",
            rewritten_sql="SELECT id, name, email FROM users",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "invalid original order by"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["confidence"], "MEDIUM")
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_CONSTANT_ORDER_BY_REMOVAL")

    def test_same_column_or_to_in_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users WHERE status IN ('ACTIVE', 'PENDING') ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_OR_TO_IN")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_OR_TO_IN_EQUIVALENT")

    def test_case_when_true_simplification_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC",
            rewritten_sql="SELECT id, status AS status FROM users ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_CASE_WHEN_TRUE")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_CASE_WHEN_TRUE_EQUIVALENT")

    def test_coalesce_identity_simplification_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC",
            rewritten_sql="SELECT id, status AS status FROM users ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_COALESCE_IDENTITY")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_COALESCE_IDENTITY_EQUIVALENT")

    def test_constant_expression_folding_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users WHERE id = 2 ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_CONSTANT_EXPRESSION_FOLDING")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_CONSTANT_EXPRESSION_EQUIVALENT")

    def test_distinct_from_alias_cleanup_is_treated_as_semantically_stable(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT DISTINCT u.status FROM users u ORDER BY u.status",
            rewritten_sql="SELECT DISTINCT status FROM users ORDER BY status",
            equivalence={
                "checked": True,
                "method": "sql_semantic_compare_v1",
                "rowCount": {"status": "ERROR", "error": "aggregate compare unsupported"},
                "evidenceRefs": [],
            },
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["equivalenceOverrideApplied"])
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_SAFE_BASELINE_DISTINCT_FROM_ALIAS_CLEANUP")
        self.assertIn("SEMANTIC_SAFE_BASELINE_DISTINCT_FROM_ALIAS_CLEANUP", result["reasons"])
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_simple_select_wrapper_collapse_is_treated_as_semantically_equivalent(self) -> None:
        result = build_semantic_equivalence(
            original_sql="""
                SELECT id, name, email, status, created_at, updated_at
                FROM (
                    SELECT id, name, email, status, created_at, updated_at
                    FROM users
                    WHERE status = #{status}
                      AND created_at >= #{createdAfter}
                ) filtered_users
                ORDER BY created_at DESC
            """,
            rewritten_sql="""
                SELECT id, name, email, status, created_at, updated_at
                FROM users
                WHERE status = #{status}
                  AND created_at >= #{createdAfter}
                ORDER BY created_at DESC
            """,
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
        self.assertEqual(result["checks"]["predicate"]["status"], "PASS")
        self.assertEqual(result["checks"]["ordering"]["status"], "PASS")

    def test_comment_only_difference_does_not_change_semantic_result(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            rewritten_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} /* COUNT query - LIMIT not applicable */",
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
        self.assertEqual(result["checks"]["predicate"]["status"], "PASS")
        self.assertEqual(result["checks"]["predicate"]["status"], "PASS")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_STABLE")
        self.assertFalse(result["equivalenceOverrideApplied"])

    def test_large_limit_removal_is_treated_as_db_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users ORDER BY created_at DESC LIMIT 1000000",
            rewritten_sql="SELECT id, name FROM users ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_DB_EQUIVALENCE_LARGE_LIMIT_REMOVAL")
        self.assertEqual(result["checks"]["pagination"]["reasonCode"], "SEMANTIC_PAGINATION_LARGE_LIMIT_EQUIVALENT")

    def test_null_comparison_normalization_is_treated_as_db_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users WHERE email != NULL ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users WHERE email IS NOT NULL ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_DB_EQUIVALENCE_NULL_COMPARISON_NORMALIZATION")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_NULL_COMPARISON_EQUIVALENT")

    def test_distinct_on_simplification_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT DISTINCT ON (status) status FROM users ORDER BY status",
            rewritten_sql="SELECT DISTINCT status FROM users ORDER BY status",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_DISTINCT_ON_SIMPLIFICATION")
        self.assertEqual(result["checks"]["projection"]["reasonCode"], "SEMANTIC_PROJECTION_DISTINCT_ON_EQUIVALENT")

    def test_exists_self_rewrite_is_treated_as_semantically_equivalent_with_exact_fingerprint(self) -> None:
        result = build_semantic_equivalence(
            original_sql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id) ORDER BY created_at DESC",
            rewritten_sql="SELECT id, name FROM users u ORDER BY created_at DESC",
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
        self.assertEqual(result["equivalenceOverrideRule"], "SEMANTIC_KNOWN_EQUIVALENCE_EXISTS_SELF_REWRITE")
        self.assertEqual(result["checks"]["predicate"]["reasonCode"], "SEMANTIC_PREDICATE_EXISTS_SELF_EQUIVALENT")

    def test_union_wrapper_collapse_is_treated_as_semantically_equivalent(self) -> None:
        result = build_semantic_equivalence(
            original_sql=(
                "SELECT id, status, shipped_at FROM ("
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'"
                ") su ORDER BY status, id"
            ),
            rewritten_sql=(
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
            ),
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
        self.assertEqual(result["checks"]["ordering"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
