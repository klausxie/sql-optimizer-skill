from __future__ import annotations

import unittest

from sqlopt.platforms.sql.candidate_generation_policy import (
    build_candidate_generation_diagnostics,
    recover_candidates_from_shape,
)
from sqlopt.platforms.sql.candidate_generation_support import (
    dynamic_filter_from_alias_cleanup_sql,
    simple_where_predicate_signature,
)


class CandidateGenerationPolicyTest(unittest.TestCase):
    def test_simple_where_predicate_signature_is_order_insensitive(self) -> None:
        left = simple_where_predicate_signature(
            "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}"
        )
        right = simple_where_predicate_signature(
            "SELECT COUNT(*) FROM users WHERE created_at >= #{createdAfter} AND status = #{status}"
        )

        self.assertIsNotNone(left)
        self.assertEqual(left, right)

    def test_recover_candidates_from_shape_handles_dynamic_count_wrapper(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.user.advanced.countUsersFilteredWrapped#v4",
            "SELECT COUNT(1) FROM ( SELECT id FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ) filtered_users",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_DYNAMIC_COUNT_WRAPPER_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
        )

    def test_dynamic_filter_from_alias_cleanup_sql_removes_redundant_table_alias(self) -> None:
        cleaned = dynamic_filter_from_alias_cleanup_sql(
            "SELECT id, name, email, status, created_at, updated_at FROM users u WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
        )

        self.assertEqual(
            cleaned,
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
        )

    def test_recover_candidates_from_shape_handles_dynamic_filter_from_alias_cleanup(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.user.advanced.listUsersFilteredTableAliased#v18",
            "SELECT id, name, email, status, created_at, updated_at FROM users u WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
        )

    def test_recover_candidates_from_shape_handles_simple_cte(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.user.cte#v1",
            "WITH recent_users AS (SELECT id, created_at FROM users) SELECT id, created_at FROM recent_users ORDER BY created_at DESC",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "INLINE_SIMPLE_CTE_RECOVERED")
        self.assertEqual(recovered[0]["rewrittenSql"], "SELECT id, created_at FROM users ORDER BY created_at DESC")

    def test_build_candidate_generation_diagnostics_marks_low_value_aggregation_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.aggregate#v1",
            original_sql="SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY status",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total FROM orders WHERE status IS NOT NULL GROUP BY status ORDER BY status",
                    "rewriteStrategy": "ADD_FILTER",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY status LIMIT 1000",
                    "rewriteStrategy": "ADD_LIMIT",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total FROM orders WHERE status IS NOT NULL GROUP BY status ORDER BY status",
                    "rewriteStrategy": "ADD_FILTER",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY status LIMIT 1000",
                    "rewriteStrategy": "ADD_LIMIT",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["lowValueCandidateCount"], 2)
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_distinct_to_group_by_index_scan(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
            original_sql="SELECT DISTINCT status FROM users ORDER BY status",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "GROUP_BY_INDEX_SCAN",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "GROUP_BY_INDEX_SCAN",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": [], "statementType": "SELECT"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_replace_distinct_with_group_by(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
            original_sql="SELECT DISTINCT status FROM users ORDER BY status",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "REPLACE_DISTINCT_WITH_GROUP_BY",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "REPLACE_DISTINCT_WITH_GROUP_BY",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": [], "statementType": "SELECT"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_having_index_hint_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrderUserCountsHaving#v8",
            original_sql="SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
                    "rewriteStrategy": "Index hint for GROUP BY optimization using composite index on (user_id, created_at)",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
                    "rewriteStrategy": "Index hint for GROUP BY optimization using composite index on (user_id, created_at)",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": [], "statementType": "SELECT"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_recover_candidates_from_shape_handles_having_wrapper(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.order.having#v1",
            "SELECT user_id, COUNT(*) AS total FROM ( SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ) oh ORDER BY user_id",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
        )

    def test_recover_candidates_from_shape_handles_dynamic_filter_wrapper_with_outer_order(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.user.advanced.listUsersFilteredWrapped#v15",
            "SELECT id, name, email, status, created_at, updated_at FROM ( SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ) filtered_users ORDER BY created_at DESC",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_REDUNDANT_SUBQUERY_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
        )

    def test_recover_candidates_from_shape_handles_static_paged_wrapper_with_outer_limit(self) -> None:
        recovered = recover_candidates_from_shape(
            "demo.shipment.harness.listRecentShipmentsPaged#v4",
            "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM ( SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments ) s ORDER BY shipped_at DESC LIMIT 50",
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_REDUNDANT_SUBQUERY_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments ORDER BY shipped_at DESC LIMIT 50",
        )

    def test_build_candidate_generation_diagnostics_marks_window_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.window#v1",
            original_sql="SELECT order_no, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn FROM orders",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_WINDOW")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_dynamic_paged_include_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.include#v1",
            original_sql="SELECT id, name FROM users ORDER BY created_at DESC LIMIT 100",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_DYNAMIC_PAGED_INCLUDE")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_group_by_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.aggregateOrdersByStatus#v5",
            original_sql="SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status ORDER BY status",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_GROUP_BY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_having_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrderUserCountsHaving#v8",
            original_sql="SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1 ORDER BY user_id",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_HAVING")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_distinct_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
            original_sql="SELECT DISTINCT status FROM users ORDER BY status",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_DISTINCT")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_dml_set_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.updateUserSelective#v9",
            original_sql="UPDATE users <set> <if test='name != null'>name = #{name},</if> </set> WHERE id = #{id}",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["SET", "IF"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_DML_SET")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_marks_dml_foreach_empty_reason(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.markShipmentsDeleted#v5",
            original_sql="UPDATE shipments SET deleted = 1 WHERE id IN <foreach collection='ids' item='id' open='(' separator=',' close=')'>#{id}</foreach>",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "NO_SAFE_BASELINE_DML_FOREACH")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_text_fallback_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.ids#v1",
            original_sql="SELECT id, order_id FROM shipments",
            raw_candidates=[
                {
                    "id": "fallback:text",
                    "rewrittenSql": "plain english explanation",
                    "rewriteStrategy": "opencode_text_fallback",
                }
            ],
            valid_candidates=[
                {
                    "id": "fallback:text",
                    "rewrittenSql": "plain english explanation",
                    "rewriteStrategy": "opencode_text_fallback",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "TEXT_ONLY_FALLBACK")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_speculative_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "NO_CHANGE",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} /*+ INDEX(users idx_users_status_created) */",
                    "rewriteStrategy": "ADD_INDEX_HINT",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} AND created_at IS NOT NULL",
                    "rewriteStrategy": "ADD_NOT_NULL_CHECK",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "NO_CHANGE",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} /*+ INDEX(users idx_users_status_created) */",
                    "rewriteStrategy": "ADD_INDEX_HINT",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} AND created_at IS NOT NULL",
                    "rewriteStrategy": "ADD_NOT_NULL_CHECK",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 3)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_count_to_exists(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT EXISTS(SELECT 1 FROM users WHERE status = #{status} AND created_at >= #{createdAfter} LIMIT 1)",
                    "rewriteStrategy": "count_to_exists",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT EXISTS(SELECT 1 FROM users WHERE status = #{status} AND created_at >= #{createdAfter} LIMIT 1)",
                    "rewriteStrategy": "count_to_exists",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_union_simplification(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.listShipmentStatusUnion#v6",
            original_sql=(
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, status, shipped_at FROM shipments WHERE status IN ('SHIPPED', 'DELIVERED') ORDER BY status, id",
                    "rewriteStrategy": "SIMPLIFY_UNION",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, status, shipped_at FROM shipments WHERE status IN ('SHIPPED', 'DELIVERED') ORDER BY status, id",
                    "rewriteStrategy": "SIMPLIFY_UNION",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_distinct_to_groupby(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
            original_sql="SELECT DISTINCT status FROM users ORDER BY status",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "DISTINCT_TO_GROUPBY",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "DISTINCT_TO_GROUPBY",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_distinct_to_groupby_natural_language_strategy(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
            original_sql="SELECT DISTINCT status FROM users ORDER BY status",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "Replace DISTINCT with GROUP BY for clearer semantics; enables index-only scan on idx_users_status_created",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status FROM users GROUP BY status ORDER BY status",
                    "rewriteStrategy": "Replace DISTINCT with GROUP BY for clearer semantics; enables index-only scan on idx_users_status_created",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_window_clause_extract(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrderAmountWindowRanks#v7",
            original_sql=(
                "SELECT order_no, amount, "
                "ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS row_rank "
                "FROM orders"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "SELECT order_no, amount, ROW_NUMBER() OVER w AS row_rank "
                        "FROM orders WINDOW w AS (PARTITION BY user_id ORDER BY created_at DESC)"
                    ),
                    "rewriteStrategy": "window_clause_extract",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "SELECT order_no, amount, ROW_NUMBER() OVER w AS row_rank "
                        "FROM orders WINDOW w AS (PARTITION BY user_id ORDER BY created_at DESC)"
                    ),
                    "rewriteStrategy": "window_clause_extract",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_group_by_order_by_removal(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.aggregateOrdersByStatus#v5",
            original_sql=(
                "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount "
                "FROM orders GROUP BY status ORDER BY status"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status",
                    "rewriteStrategy": "remove_redundant_order_by",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT status, COUNT(*) AS total, SUM(amount) AS total_amount FROM orders GROUP BY status",
                    "rewriteStrategy": "remove_redundant_order_by",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": []},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dml_speculative_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.updateOrderStatusByNos#v6",
            original_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = 'pending' WHERE order_no IN ('ORD001', 'ORD002')",
                    "rewriteStrategy": "parameter_substitution",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "UPDATE orders SET status = 'completed' WHERE order_no IN (SELECT DISTINCT order_no FROM orders WHERE created_at > CURRENT_DATE - INTERVAL '7 days')",
                    "rewriteStrategy": "batch_optimization",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = 'pending' WHERE order_no IN ('ORD001', 'ORD002')",
                    "rewriteStrategy": "parameter_substitution",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "UPDATE orders SET status = 'completed' WHERE order_no IN (SELECT DISTINCT order_no FROM orders WHERE created_at > CURRENT_DATE - INTERVAL '7 days')",
                    "rewriteStrategy": "batch_optimization",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_null_safe_update_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.updateUserSelective#v9",
            original_sql="UPDATE users SET name = #{name}, email = #{email}, status = #{status}, updated_at = #{updatedAt} WHERE id = #{id}",
            raw_candidates=[
                {
                    "id": "c3",
                    "rewrittenSql": "UPDATE users SET name = COALESCE(#{name}, name), email = COALESCE(#{email}, email), status = COALESCE(#{status}, status), updated_at = COALESCE(#{updatedAt}, updated_at) WHERE id = #{id}",
                    "rewriteStrategy": "NULL_SAFE_UPDATE",
                }
            ],
            valid_candidates=[
                {
                    "id": "c3",
                    "rewrittenSql": "UPDATE users SET name = COALESCE(#{name}, name), email = COALESCE(#{email}, email), status = COALESCE(#{status}, status), updated_at = COALESCE(#{updatedAt}, updated_at) WHERE id = #{id}",
                    "rewriteStrategy": "NULL_SAFE_UPDATE",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["SET", "IF"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_array_parameter_update_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.markShipmentsDeleted#v5",
            original_sql="UPDATE shipments SET status = 'DELETED' WHERE id IN #{id}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id = ANY(#{id})",
                    "rewriteStrategy": "IN_TO_ANY",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id = ANY(#{id})",
                    "rewriteStrategy": "IN_TO_ANY",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_template_fix_update_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.markShipmentsDeleted#v5",
            original_sql="UPDATE shipments SET status = 'DELETED' WHERE id IN #{id}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection='id' item='item' open='(' separator=',' close=')'>#{item}</foreach>",
                    "rewriteStrategy": "template_fix",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "<if test='id != null and id.size() > 0'>UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection='id' item='item' open='(' separator=',' close=')'>#{item}</foreach></if>",
                    "rewriteStrategy": "null_safe_wrapper",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection='id' item='item' open='(' separator=',' close=')'>#{item}</foreach>",
                    "rewriteStrategy": "template_fix",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "<if test='id != null and id.size() > 0'>UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection='id' item='item' open='(' separator=',' close=')'>#{item}</foreach></if>",
                    "rewriteStrategy": "null_safe_wrapper",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_dynamic_sql_fix_update_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.markShipmentsDeleted#v5",
            original_sql="UPDATE shipments SET status = 'DELETED' WHERE id IN #{id}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection=\"id\" item=\"item\" open=\"(\" separator=\",\" close=\")\">#{item}</foreach>",
                    "rewriteStrategy": "dynamic_sql_fix",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE <if test=\"id != null\">id IN <foreach collection=\"id\" item=\"item\" open=\"(\" separator=\",\" close=\")\">#{item}</foreach></if><if test=\"id == null\">1=0</if>",
                    "rewriteStrategy": "null_safe_rewrite",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id IN <foreach collection=\"id\" item=\"item\" open=\"(\" separator=\",\" close=\")\">#{item}</foreach>",
                    "rewriteStrategy": "dynamic_sql_fix",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE <if test=\"id != null\">id IN <foreach collection=\"id\" item=\"item\" open=\"(\" separator=\",\" close=\")\">#{item}</foreach></if><if test=\"id == null\">1=0</if>",
                    "rewriteStrategy": "null_safe_rewrite",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_fix_syntax_update_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.updateOrderStatusByNos#v6",
            original_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN <foreach collection=\"orderNos\" item=\"no\" open=\"(\" separator=\",\" close=\")\">#{no}</foreach>",
                    "rewriteStrategy": "fix_syntax",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN <foreach collection=\"orderNos\" item=\"no\" open=\"(\" separator=\",\" close=\")\">#{no}</foreach>",
                    "rewriteStrategy": "fix_syntax",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dml_candidates_with_embedded_mybatis_tags(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.updateOrderStatusByNos#v6",
            original_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN <foreach item='item' collection='orderNo' open='(' separator=',' close=')'>#{item}</foreach>",
                    "rewriteStrategy": "safe",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN <foreach item='item' collection='orderNo' open='(' separator=',' close=')'>#{item}</foreach>",
                    "rewriteStrategy": "safe",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_parenthesized_foreach_placeholder_update_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.updateOrderStatusByNos#v6",
            original_sql="UPDATE orders SET status = #{status} WHERE order_no IN #{orderNo}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN (#{orderNo})",
                    "rewriteStrategy": "template_fix",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE orders SET status = #{status} WHERE order_no IN (#{orderNo})",
                    "rewriteStrategy": "template_fix",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_single_value_foreach_update_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.shipment.harness.markShipmentsDeleted#v5",
            original_sql="UPDATE shipments SET status = 'DELETED' WHERE id IN #{id}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id = #{id}",
                    "rewriteStrategy": "SIMPLIFY_IN_CLAUSE",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "UPDATE shipments SET status = 'DELETED' WHERE id = #{id}",
                    "rewriteStrategy": "SIMPLIFY_IN_CLAUSE",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["FOREACH"], "statementType": "UPDATE"},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_limit_addition(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} LIMIT 1000000",
                    "rewriteStrategy": "LIMIT_ADDITION",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} LIMIT 1000000",
                    "rewriteStrategy": "LIMIT_ADDITION",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_stable_order_and_time_filter(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.findUsersByKeyword#v8",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC, id LIMIT 100",
                    "rewriteStrategy": "ADD_STABLE_ORDER",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') AND created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "ADD_TIME_FILTER",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC, id LIMIT 100",
                    "rewriteStrategy": "ADD_STABLE_ORDER",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') AND created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "ADD_TIME_FILTER",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["BIND", "INCLUDE", "WHERE", "CHOOSE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_predicate_rewrites(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.findUsersByKeyword#v8",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (LOWER(name) LIKE LOWER(#{keywordPattern}) OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "STANDARDIZE_ILIKE",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status}) AND status != 'DELETED' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "SIMPLIFY_OR",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (LOWER(name) LIKE LOWER(#{keywordPattern}) OR status = #{status} OR status != 'DELETED') ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "STANDARDIZE_ILIKE",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status}) AND status != 'DELETED' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "SIMPLIFY_OR",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["BIND", "INCLUDE", "WHERE", "CHOOSE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_comment_only_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} /* COUNT query - LIMIT not applicable */",
                    "rewriteStrategy": "COMMENT_ADDITION",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter} /* COUNT query - LIMIT not applicable */",
                    "rewriteStrategy": "COMMENT_ADDITION",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_limit_when_query_is_rewritten(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.findUsersByKeyword#v8",
            original_sql=(
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') "
                "ORDER BY created_at DESC"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND status != 'DELETED' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "CONDITION_SIMPLIFY_WITH_LIMIT",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND status != 'DELETED' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "CONDITION_SIMPLIFY_WITH_LIMIT",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["BIND", "WHERE", "CHOOSE", "INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_subquery_pushdown(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrdersWithUsersPaged#v3",
            original_sql=(
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) AND o.status = #{status} "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM orders o JOIN (SELECT id, name, email FROM users WHERE name ILIKE CONCAT('%', #{keyword}, '%') OR email ILIKE CONCAT('%', #{keyword}, '%')) u ON u.id = o.user_id WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "Push user filter into subquery to reduce join rows early",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM orders o JOIN (SELECT id, name, email FROM users WHERE name ILIKE CONCAT('%', #{keyword}, '%') OR email ILIKE CONCAT('%', #{keyword}, '%')) u ON u.id = o.user_id WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "Push user filter into subquery to reduce join rows early",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_driving_table_change(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrdersWithUsersPaged#v3",
            original_sql=(
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) AND o.status = #{status} "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM users u JOIN orders o ON o.user_id = u.id AND o.status = #{status} WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "DRIVING_TABLE_CHANGE",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM users u JOIN orders o ON o.user_id = u.id AND o.status = #{status} WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "DRIVING_TABLE_CHANGE",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_join_predicate_pushdown(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrdersWithUsersPaged#v3",
            original_sql=(
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) AND o.status = #{status} "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM orders o JOIN users u ON u.id = o.user_id AND (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "JOIN_PREDICATE_PUSHDOWN",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email FROM orders o JOIN users u ON u.id = o.user_id AND (u.name ILIKE CONCAT('%', #{keyword}, '%') OR u.email ILIKE CONCAT('%', #{keyword}, '%')) WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}",
                    "rewriteStrategy": "JOIN_PREDICATE_PUSHDOWN",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_static_include_paged_speculative_filters(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listUsersRecentPaged#v5",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "INDEX_ORDER_BY",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status IS NOT NULL ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "ADD_FILTER_INDEX",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "TIME_FILTER_INDEX",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "INDEX_ORDER_BY",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status IS NOT NULL ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "ADD_FILTER_INDEX",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at DESC LIMIT 100",
                    "rewriteStrategy": "TIME_FILTER_INDEX",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 3)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_static_include_paged_offset_zero(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listUsersRecentPaged#v5",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100 OFFSET 0",
                    "rewriteStrategy": "explicit_pagination_offset",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users ORDER BY created_at DESC LIMIT 100 OFFSET 0",
                    "rewriteStrategy": "explicit_pagination_offset",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_recovers_dynamic_filter_select_cleanup(self) -> None:
        original_sql = (
            "SELECT id AS id, name AS name, email AS email, status AS status, created_at AS created_at, updated_at AS updated_at "
            "FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC"
        )
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.listUsersFilteredAliased#v17",
            original_sql=original_sql,
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": f"{original_sql} LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT",
                },
                {
                    "id": "c2",
                    "rewrittenSql": f"{original_sql} LIMIT #{{limit}} OFFSET #{{offset}}",
                    "rewriteStrategy": "ADD_PAGINATION",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": f"{original_sql} LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT",
                },
                {
                    "id": "c2",
                    "rewrittenSql": f"{original_sql} LIMIT #{{limit}} OFFSET #{{offset}}",
                    "rewriteStrategy": "ADD_PAGINATION",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 2)
        self.assertEqual(diagnostics["recoveryReason"], "SAFE_BASELINE_REPLACED_LOW_VALUE")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED")
        self.assertEqual(
            recovered[0]["rewrittenSql"],
            "SELECT id, name, email, status, created_at, updated_at FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ORDER BY created_at DESC",
        )

    def test_build_candidate_generation_diagnostics_prunes_foreach_speculative_candidates(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.findOrdersByNos#v1",
            original_sql="SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = ? LIMIT 1000",
                    "rewriteStrategy": "ADD_LIMIT_PARAMETERIZED",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (?) LIMIT 500",
                    "rewriteStrategy": "ADD_LIMIT_WITH_IN_CLAUSE",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo} LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT_PRESERVE_DYNAMIC",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = ? LIMIT 1000",
                    "rewriteStrategy": "ADD_LIMIT_PARAMETERIZED",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (?) LIMIT 500",
                    "rewriteStrategy": "ADD_LIMIT_WITH_IN_CLAUSE",
                },
                {
                    "id": "c3",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo} LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT_PRESERVE_DYNAMIC",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 3)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_single_placeholder_equality(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.findOrdersByNos#v1",
            original_sql="SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo}",
                    "rewriteStrategy": "EXPLICIT_COLUMN_REFERENCE",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo}",
                    "rewriteStrategy": "EXPLICIT_COLUMN_REFERENCE",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_cte_rewrite(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrdersWithUsersPaged#v3",
            original_sql=(
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE #{keywordFilter} AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "WITH user_matches AS (SELECT id FROM users WHERE name ILIKE CONCAT('%', #{keyword}, '%') OR email ILIKE CONCAT('%', #{keyword}, '%')) "
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id JOIN user_matches um ON um.id = u.id "
                        "WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
                    ),
                    "rewriteStrategy": "CTE_FOR_FILTER",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "WITH user_matches AS (SELECT id FROM users WHERE name ILIKE CONCAT('%', #{keyword}, '%') OR email ILIKE CONCAT('%', #{keyword}, '%')) "
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id JOIN user_matches um ON um.id = u.id "
                        "WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
                    ),
                    "rewriteStrategy": "CTE_FOR_FILTER",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_union_rewrite(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.listOrdersWithUsersPaged#v3",
            original_sql=(
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE #{keywordFilter} AND o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') AND o.status = #{status}) "
                        "UNION ALL "
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id WHERE (u.email ILIKE CONCAT('%', #{keyword}, '%') AND o.status = #{status}) "
                        "ORDER BY created_at DESC LIMIT #{limit} OFFSET #{offset}"
                    ),
                    "rewriteStrategy": "OR_TO_UNION_ALL_WITH_DEDUP",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": (
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id WHERE (u.name ILIKE CONCAT('%', #{keyword}, '%') AND o.status = #{status}) "
                        "UNION ALL "
                        "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, u.name AS user_name, u.email AS user_email "
                        "FROM orders o JOIN users u ON u.id = o.user_id WHERE (u.email ILIKE CONCAT('%', #{keyword}, '%') AND o.status = #{status}) "
                        "ORDER BY created_at DESC LIMIT #{limit} OFFSET #{offset}"
                    ),
                    "rewriteStrategy": "OR_TO_UNION_ALL_WITH_DEDUP",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_static_include_speculative_filter_and_fetch(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.listUsers#v1",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' ORDER BY created_at DESC FETCH FIRST 1000 ROWS ONLY",
                    "rewriteStrategy": "ADD_TIME_FILTER_AND_LIMIT",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' ORDER BY created_at DESC FETCH FIRST 1000 ROWS ONLY",
                    "rewriteStrategy": "ADD_TIME_FILTER_AND_LIMIT",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_static_include_limit_only(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.listUsers#v1",
            original_sql="SELECT id, name, email, status, created_at, updated_at FROM users",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT_ONLY",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, name, email, status, created_at, updated_at FROM users LIMIT 100",
                    "rewriteStrategy": "ADD_LIMIT_ONLY",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_in_to_single_value_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.findOrdersByNos#v1",
            original_sql="SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo}",
                    "rewriteStrategy": "SPECIFY_CONDITION_ONLY",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo}",
                    "rewriteStrategy": "SPECIFY_CONDITION_ONLY",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_foreach_fetch_first_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.order.harness.findOrdersByNos#v1",
            original_sql="SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no IN (#{orderNo})",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo} FETCH FIRST 1 ROWS ONLY",
                    "rewriteStrategy": "STANDARD_LIMIT",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE order_no = #{orderNo} FETCH FIRST 1 ROWS ONLY",
                    "rewriteStrategy": "STANDARD_LIMIT",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_keeps_dynamic_filter_canonical_count_candidate(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "COUNT_CONSTANT_OPTIMIZATION",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "COUNT_CONSTANT_OPTIMIZATION",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertIsNone(diagnostics["degradationKind"])
        self.assertEqual(diagnostics["acceptedCandidateCount"], 1)
        self.assertEqual(diagnostics["prunedLowValueCount"], 0)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_prunes_dynamic_filter_predicate_reorder(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE created_at >= #{createdAfter} AND status = #{status}",
                    "rewriteStrategy": "REORDER_WHERE_CLAUSE",
                }
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE created_at >= #{createdAfter} AND status = #{status}",
                    "rewriteStrategy": "REORDER_WHERE_CLAUSE",
                }
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "ONLY_LOW_VALUE_CANDIDATES")
        self.assertEqual(diagnostics["acceptedCandidateCount"], 0)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(diagnostics["recoveryReason"], "LOW_VALUE_PRUNED_TO_EMPTY")
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_keeps_dynamic_filter_count_candidate_but_prunes_reorder(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersDirectFiltered#v3",
            original_sql="SELECT COUNT(*) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
            raw_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "SIMPLIFY_COUNT_EXPRESSION",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE created_at >= #{createdAfter} AND status = #{status}",
                    "rewriteStrategy": "REORDER_WHERE_CLAUSE",
                },
            ],
            valid_candidates=[
                {
                    "id": "c1",
                    "rewrittenSql": "SELECT COUNT(1) FROM users WHERE status = #{status} AND created_at >= #{createdAfter}",
                    "rewriteStrategy": "SIMPLIFY_COUNT_EXPRESSION",
                },
                {
                    "id": "c2",
                    "rewrittenSql": "SELECT COUNT(*) FROM users WHERE created_at >= #{createdAfter} AND status = #{status}",
                    "rewriteStrategy": "REORDER_WHERE_CLAUSE",
                },
            ],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertIsNone(diagnostics["degradationKind"])
        self.assertEqual(diagnostics["acceptedCandidateCount"], 1)
        self.assertEqual(diagnostics["prunedLowValueCount"], 1)
        self.assertEqual(recovered, [])

    def test_build_candidate_generation_diagnostics_recovers_dynamic_count_wrapper_from_empty(self) -> None:
        diagnostics, recovered = build_candidate_generation_diagnostics(
            sql_key="demo.user.advanced.countUsersFilteredWrapped#v4",
            original_sql="SELECT COUNT(1) FROM ( SELECT id FROM users WHERE status = #{status} AND created_at >= #{createdAfter} ) filtered_users",
            raw_candidates=[],
            valid_candidates=[],
            trace={"degrade_reason": None},
            sql_unit={"dynamicFeatures": ["WHERE", "IF"]},
        )

        self.assertEqual(diagnostics["degradationKind"], "EMPTY_CANDIDATES")
        self.assertEqual(diagnostics["recoveryReason"], "SAFE_BASELINE_SHAPE_RECOVERY")
        self.assertEqual(diagnostics["recoveryStrategy"], "REMOVE_DYNAMIC_COUNT_WRAPPER_RECOVERED")
        self.assertEqual(diagnostics["recoveredCandidateCount"], 1)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["rewriteStrategy"], "REMOVE_DYNAMIC_COUNT_WRAPPER_RECOVERED")


if __name__ == "__main__":
    unittest.main()
