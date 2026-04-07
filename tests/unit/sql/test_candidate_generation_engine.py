from __future__ import annotations

import unittest

from sqlopt.platforms.sql.candidate_generation_engine import evaluate_candidate_generation


class CandidateGenerationEngineTest(unittest.TestCase):
    def test_recovers_static_statement_select_alias_cleanup_when_candidates_missing(self) -> None:
        original_sql = (
            "SELECT id AS id, name AS name, email AS email, status AS status, "
            "created_at AS created_at, updated_at AS updated_at "
            "FROM users ORDER BY created_at DESC"
        )

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersProjectedAliases",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersProjectedAliases",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=[],
            valid_candidates=[],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(
            outcome.recovery_candidates[0]["rewriteStrategy"],
            "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
        )
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_SHAPE_RECOVERY")

    def test_replaces_low_value_static_statement_candidates_with_safe_baseline_recovery(self) -> None:
        original_sql = (
            "SELECT u.id AS id, u.name AS name, u.email AS email, u.status AS status, "
            "u.created_at AS created_at, u.updated_at AS updated_at "
            "FROM users u ORDER BY u.created_at DESC"
        )

        candidates = [
            {
                "id": "1",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id AS id, u.name AS name, u.email AS email, u.status AS status, "
                    "u.created_at AS created_at, u.updated_at AS updated_at "
                    "FROM users u WHERE u.status IS NOT NULL ORDER BY u.created_at DESC"
                ),
                "rewriteStrategy": "predicate_pushdown",
            },
            {
                "id": "2",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id AS id, u.name AS name, u.email AS email, u.status AS status, "
                    "u.created_at AS created_at, u.updated_at AS updated_at "
                    "FROM users u ORDER BY u.created_at DESC LIMIT 1000"
                ),
                "rewriteStrategy": "limit_optimization",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersProjectedQualifiedAliases",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersProjectedQualifiedAliases",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_REPLACED_LOW_VALUE")
        self.assertIn(
            outcome.recovery_candidates[0]["rewriteStrategy"],
            {"REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED", "REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED"},
        )

    def test_prefers_from_alias_safe_baseline_recovery_when_accepted_candidate_drops_ordering(self) -> None:
        original_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
        )

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersFilteredPredicateAliased",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersFilteredPredicateAliased",
                "sql": original_sql,
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            },
            raw_candidates=[
                {
                    "id": "2",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id, name, email, status, created_at, updated_at "
                        "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter}"
                    ),
                    "rewriteStrategy": "REMOVE_REDUNDANT_SORT",
                }
            ],
            valid_candidates=[
                {
                    "id": "2",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id, name, email, status, created_at, updated_at "
                        "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter}"
                    ),
                    "rewriteStrategy": "REMOVE_REDUNDANT_SORT",
                }
            ],
            trace={},
        )

        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(
            outcome.recovery_candidates[0]["id"],
            "demo.user.advanced.listUsersFilteredPredicateAliased:llm:recovered_dynamic_filter_from_alias_cleanup",
        )
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_ORDER_PRESERVING_RECOVERY")

    def test_prefers_safe_baseline_recovery_when_accepted_candidate_only_changes_single_table_qualifiers(self) -> None:
        cases = (
            (
                "demo.user.advanced.listUsersFilteredPredicateAliased",
                (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
                ),
                {
                    "id": "opt-002",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id, name, email, status, created_at, updated_at "
                        "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
                    ),
                    "rewriteStrategy": "SIMPLIFY_ALIAS",
                },
            ),
            (
                "demo.user.advanced.listUsersFilteredTableAliased",
                (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users u WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
                ),
                {
                    "id": "opt-002",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT u.id, u.name, u.email, u.status, u.created_at, u.updated_at "
                        "FROM users u WHERE u.status = #{status} AND u.created_at >= #{createdAfter} ORDER BY u.created_at DESC"
                    ),
                    "rewriteStrategy": "explicit_qualification",
                },
            ),
        )

        for sql_key, original_sql, accepted_candidate in cases:
            with self.subTest(sql_key=sql_key):
                outcome = evaluate_candidate_generation(
                    sql_key=sql_key,
                    original_sql=original_sql,
                    sql_unit={
                        "sqlKey": sql_key,
                        "sql": original_sql,
                        "dynamicFeatures": ["WHERE", "IF"],
                        "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
                    },
                    raw_candidates=[accepted_candidate],
                    valid_candidates=[accepted_candidate],
                    trace={},
                )

                self.assertEqual(len(outcome.accepted_candidates), 0)
                self.assertEqual(len(outcome.recovery_candidates), 1)
                self.assertEqual(
                    outcome.recovery_candidates[0]["id"],
                    f"{sql_key}:llm:recovered_dynamic_filter_from_alias_cleanup",
                )
                self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_REPLACED_LOW_VALUE")

    def test_prefers_select_cleanup_recovery_for_choose_filter_predicate_simplification(self) -> None:
        original_sql = (
            "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
            "FROM users WHERE (status = #{status} OR status != 'DELETED') ORDER BY created_at DESC"
        )

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersFilteredAliasedChoose",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersFilteredAliasedChoose",
                "sql": original_sql,
                "dynamicFeatures": ["WHERE", "CHOOSE"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "CHOOSE"]},
            },
            raw_candidates=[
                {
                    "id": "opt-001",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                        "FROM users WHERE status = #{status} ORDER BY created_at DESC"
                    ),
                    "rewriteStrategy": "predicate_simplification",
                },
                {
                    "id": "opt-002",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                        "FROM users WHERE status != 'DELETED' ORDER BY created_at DESC"
                    ),
                    "rewriteStrategy": "predicate_simplification",
                },
            ],
            valid_candidates=[
                {
                    "id": "opt-001",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                        "FROM users WHERE status = #{status} ORDER BY created_at DESC"
                    ),
                    "rewriteStrategy": "predicate_simplification",
                },
                {
                    "id": "opt-002",
                    "source": "llm",
                    "rewrittenSql": (
                        "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
                        "FROM users WHERE status != 'DELETED' ORDER BY created_at DESC"
                    ),
                    "rewriteStrategy": "predicate_simplification",
                },
            ],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(
            outcome.recovery_candidates[0]["id"],
            "demo.user.advanced.listUsersFilteredAliasedChoose:llm:recovered_dynamic_filter_select_cleanup",
        )

    def test_replaces_large_limit_speculation_with_safe_limit_recovery(self) -> None:
        original_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users ORDER BY created_at DESC LIMIT 1000000"
        )
        candidate = {
            "id": "opt-004",
            "source": "llm",
            "rewrittenSql": "SELECT id, name, email FROM users ORDER BY created_at DESC LIMIT 100",
            "rewriteStrategy": "column_reduction",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersLargeLimit",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersLargeLimit",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(outcome.recovery_candidates[0]["rewriteStrategy"], "REMOVE_LARGE_LIMIT_RECOVERED")
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_REPLACED_LOW_VALUE")
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_REPLACED_LOW_VALUE")

    def test_replaces_distinct_on_speculation_with_safe_distinct_on_recovery(self) -> None:
        original_sql = "SELECT DISTINCT ON (status) status FROM users ORDER BY status"
        candidate = {
            "id": "opt-distinct-on-tiebreaker",
            "source": "llm",
            "rewrittenSql": "SELECT DISTINCT ON (status) status FROM users ORDER BY status, created_at DESC",
            "rewriteStrategy": "INDEX_OPTIMIZED_ORDER_BY",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.listUsersDistinctOnStatus",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.user.advanced.listUsersDistinctOnStatus",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 1)
        self.assertEqual(
            outcome.recovery_candidates[0]["rewriteStrategy"],
            "SIMPLIFY_DISTINCT_ON_RECOVERED",
        )
        self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_REPLACED_LOW_VALUE")

    def test_prefers_groupby_alias_cleanup_recovery_over_generic_select_cleanup(self) -> None:
        cases = (
            (
                "demo.order.harness.aggregateOrdersByStatusAliased",
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount FROM orders o GROUP BY o.status ORDER BY o.status",
                "demo.order.harness.aggregateOrdersByStatusAliased:llm:recovered_groupby_from_alias_cleanup",
                "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED",
            ),
            (
                "demo.order.harness.listOrderUserCountsHavingAliased",
                "SELECT o.user_id AS user_id, COUNT(*) AS total FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id",
                "demo.order.harness.listOrderUserCountsHavingAliased:llm:recovered_groupby_from_alias_cleanup",
                "REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED",
            ),
        )

        for sql_key, original_sql, expected_id, expected_strategy in cases:
            with self.subTest(sql_key=sql_key):
                outcome = evaluate_candidate_generation(
                    sql_key=sql_key,
                    original_sql=original_sql,
                    sql_unit={
                        "sqlKey": sql_key,
                        "sql": original_sql,
                        "dynamicFeatures": [],
                        "dynamicTrace": {"statementFeatures": []},
                    },
                    raw_candidates=[],
                    valid_candidates=[],
                    trace={},
                )

                self.assertEqual(len(outcome.accepted_candidates), 0)
                self.assertEqual(len(outcome.recovery_candidates), 1)
                self.assertEqual(outcome.recovery_candidates[0]["id"], expected_id)
                self.assertEqual(outcome.recovery_candidates[0]["rewriteStrategy"], expected_strategy)
                self.assertEqual(outcome.diagnostics.recovery_reason, "SAFE_BASELINE_SHAPE_RECOVERY")


if __name__ == "__main__":
    unittest.main()
