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

    def test_does_not_recover_static_tautology_cleanup_for_choose_guarded_filter_shape(self) -> None:
        original_sql = (
            "SELECT id, name FROM users "
            "WHERE (status = 'active' OR status = 'inactive' OR 1 = 1)"
        )

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.chooseBasic",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.chooseBasic",
                "sql": original_sql,
                "templateSql": (
                    "SELECT id, name FROM users <choose>"
                    "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
                    "<when test=\"type == 'inactive'\">WHERE status = 'inactive'</when>"
                    "<otherwise>WHERE 1 = 1</otherwise>"
                    "</choose>"
                ),
                "dynamicFeatures": ["CHOOSE"],
                "dynamicTrace": {"statementFeatures": ["CHOOSE"]},
            },
            raw_candidates=[],
            valid_candidates=[],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_SAFE_BASELINE_SHAPE_MATCH")

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

    def test_prunes_keyset_pagination_for_dynamic_filter_template_with_offset(self) -> None:
        original_sql = (
            "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
            "u.name AS user_name, u.email AS user_email "
            "FROM orders o JOIN users u ON u.id = o.user_id "
            "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) "
            "AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
        )
        candidate = {
            "id": "opt-003",
            "source": "llm",
            "rewrittenSql": (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE o.status = #{status} AND (u.name ILIKE CONCAT('%', #{keyword}, '%') "
                "OR u.email ILIKE CONCAT('%', #{keyword}, '%')) "
                "ORDER BY o.created_at DESC LIMIT #{limit}"
            ),
            "rewriteStrategy": "keyset_pagination",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.order.harness.listOrdersWithUsersPaged",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.order.harness.listOrdersWithUsersPaged",
                "sql": original_sql,
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "LOW_VALUE_PRUNED_TO_EMPTY")

    def test_prunes_fulltext_search_speculation_for_dynamic_filter_template(self) -> None:
        original_sql = (
            "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
            "u.name AS user_name, u.email AS user_email "
            "FROM orders o JOIN users u ON u.id = o.user_id "
            "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) "
            "AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
        )
        candidate = {
            "id": "opt-fts",
            "source": "llm",
            "rewrittenSql": (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE MATCH(u.name, u.email) AGAINST (#{keyword} IN BOOLEAN MODE) "
                "AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            "rewriteStrategy": "fulltext_search",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.order.harness.listOrdersWithUsersPaged",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.order.harness.listOrdersWithUsersPaged",
                "sql": original_sql,
                "dynamicFeatures": ["WHERE", "IF"],
                "dynamicTrace": {"statementFeatures": ["WHERE", "IF"]},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER")

    def test_prunes_speculative_limit_addition_for_static_include_statement(self) -> None:
        original_sql = "SELECT id, name, email, status FROM users"
        candidate = {
            "id": "1",
            "source": "llm",
            "rewrittenSql": "SELECT id, name, email, status FROM users LIMIT 100",
            "rewriteStrategy": "LIMIT_ADDITION",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.multiFragmentLevel1",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.multiFragmentLevel1",
                "sql": original_sql,
                "dynamicFeatures": ["INCLUDE"],
                "dynamicTrace": {"statementFeatures": ["INCLUDE"]},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER")

    def test_prunes_in_subquery_wording_drift_variants_without_safe_baseline(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidates = [
            {
                "id": "opt-003",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'active')"
                ),
                "rewriteStrategy": "in-to-exists",
            },
            {
                "id": "opt-004",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT DISTINCT u.id, u.name FROM users u "
                    "INNER JOIN orders o ON u.id = o.user_id WHERE o.status = 'active'"
                ),
                "rewriteStrategy": "in-to-join",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")
        self.assertTrue(all(assessment.category == "UNSUPPORTED_STRATEGY" for assessment in outcome.diagnostics.low_value_assessments))

    def test_prunes_in_subquery_semantic_rewrites_without_safe_baseline(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidates = [
            {
                "id": "opt-001",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'active')"
                ),
                "rewriteStrategy": "in_subquery_to_exists",
            },
            {
                "id": "opt-002",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT DISTINCT u.id, u.name FROM users u "
                    "INNER JOIN orders o ON u.id = o.user_id WHERE o.status = 'active'"
                ),
                "rewriteStrategy": "in_subquery_to_join",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_prunes_subquery_to_exists_and_join_wording_without_safe_baseline(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidates = [
            {
                "id": "opt-001",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'active')"
                ),
                "rewriteStrategy": "subquery_to_exists",
            },
            {
                "id": "opt-002",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT DISTINCT u.id, u.name FROM users u "
                    "INNER JOIN orders o ON u.id = o.user_id WHERE o.status = 'active'"
                ),
                "rewriteStrategy": "subquery_to_join",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_mixed_low_value_pool_stays_pruned_to_empty_when_unsupported_strategy_is_present(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidates = [
            {
                "id": "opt-001",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'active')"
                ),
                "rewriteStrategy": "EXISTS_TRANSFORM",
            },
            {
                "id": "opt-002",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE u.id IN (SELECT o.user_id FROM orders o WHERE o.status = 'active' AND o.user_id IS NOT NULL)"
                ),
                "rewriteStrategy": "null_safe_in",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(
            {assessment.category for assessment in outcome.diagnostics.low_value_assessments},
            {"UNSUPPORTED_STRATEGY", "STATIC_STATEMENT_SPECULATIVE_REWRITE"},
        )

    def test_prunes_null_safe_in_variant_without_safe_baseline(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidate = {
            "id": "opt-003",
            "source": "llm",
            "rewrittenSql": (
                "SELECT u.id, u.name FROM users u "
                "WHERE u.id IN (SELECT o.user_id FROM orders o WHERE o.status = 'active' AND o.user_id IS NOT NULL)"
            ),
            "rewriteStrategy": "null_safe_in",
        }

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=[candidate],
            valid_candidates=[candidate],
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "LOW_VALUE_PRUNED_TO_EMPTY")

    def test_prunes_exists_and_join_transform_wording_drift_without_safe_baseline(self) -> None:
        original_sql = "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM orders WHERE status = 'active')"
        candidates = [
            {
                "id": "opt-001",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT u.id, u.name FROM users u "
                    "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'active')"
                ),
                "rewriteStrategy": "EXISTS_TRANSFORM",
            },
            {
                "id": "opt-002",
                "source": "llm",
                "rewrittenSql": (
                    "SELECT DISTINCT u.id, u.name FROM users u "
                    "INNER JOIN orders o ON u.id = o.user_id WHERE o.status = 'active'"
                ),
                "rewriteStrategy": "JOIN_TRANSFORM",
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.test.complex.inSubquery",
            original_sql=original_sql,
            sql_unit={
                "sqlKey": "demo.test.complex.inSubquery",
                "sql": original_sql,
                "dynamicFeatures": [],
                "dynamicTrace": {"statementFeatures": []},
            },
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY")

    def test_freezes_find_users_by_keyword_candidate_pool_classification(self) -> None:
        original_sql = (
            "SELECT id, name, email, status, created_at, updated_at "
            "FROM users AS u WHERE status != 'DELETED' ORDER BY created_at DESC"
        )
        sql_unit = {
            "sqlKey": "demo.user.advanced.findUsersByKeyword",
            "sql": original_sql,
            "templateSql": (
                "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
                "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users "
                "<where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
                "<when test=\"status != null and status != ''\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where> ORDER BY created_at DESC"
            ),
            "dynamicFeatures": ["BIND", "INCLUDE", "WHERE", "CHOOSE"],
            "dynamicTrace": {"statementFeatures": ["BIND", "INCLUDE", "WHERE", "CHOOSE"]},
        }
        candidates = [
            {
                "id": "opt-001",
                "source": "llm",
                "rewriteStrategy": "union_or_elimination",
                "rewrittenSql": (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users AS u WHERE (name ILIKE #{keywordPattern} OR status = #{status}) "
                    "AND status != 'DELETED' ORDER BY created_at DESC"
                ),
            },
            {
                "id": "opt-002",
                "source": "llm",
                "rewriteStrategy": "redundant_condition_removal",
                "rewrittenSql": (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users AS u WHERE name ILIKE #{keywordPattern} ORDER BY created_at DESC"
                ),
            },
            {
                "id": "opt-003",
                "source": "llm",
                "rewriteStrategy": "index_driven_union",
                "rewrittenSql": (
                    "SELECT id, name, email, status, created_at, updated_at "
                    "FROM users AS u WHERE name ILIKE #{keywordPattern} ORDER BY created_at DESC"
                ),
            },
        ]

        outcome = evaluate_candidate_generation(
            sql_key="demo.user.advanced.findUsersByKeyword",
            original_sql=original_sql,
            sql_unit=sql_unit,
            raw_candidates=candidates,
            valid_candidates=candidates,
            trace={},
        )

        self.assertEqual(
            outcome.diagnostics.raw_rewrite_strategies,
            ["union_or_elimination", "redundant_condition_removal", "index_driven_union"],
        )
        self.assertEqual(len(outcome.accepted_candidates), 0)
        self.assertEqual(len(outcome.recovery_candidates), 0)
        self.assertEqual(outcome.diagnostics.degradation_kind, "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(outcome.diagnostics.recovery_reason, "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER")
        self.assertEqual(
            [
                (assessment.candidate_id, assessment.category, assessment.reason)
                for assessment in outcome.diagnostics.low_value_assessments
            ],
            [
                (
                    "opt-001",
                    "SEMANTIC_RISK_REWRITE",
                    "candidate merges choose branches on a supported choose-guarded filter without a template-preserving safe path",
                ),
                (
                    "opt-002",
                    "NO_SAFE_BASELINE_MATCH",
                    "candidate rewrites choose-guarded filter predicates but does not match any supported template-preserving baseline",
                ),
                (
                    "opt-003",
                    "UNSUPPORTED_STRATEGY",
                    "candidate uses an unsupported union/index strategy on a supported choose-guarded filter",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
