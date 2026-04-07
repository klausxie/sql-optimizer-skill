from __future__ import annotations

from sqlopt.platforms.sql.candidate_generation_support import (
    boolean_tautology_cleanup_sql,
    case_when_true_cleanup_sql,
    coalesce_identity_cleanup_sql,
    distinct_on_cleanup_sql,
    expression_folding_cleanup_sql,
    exists_self_cleanup_sql,
    in_list_single_value_cleanup_sql,
    limit_large_cleanup_sql,
    null_comparison_cleanup_sql,
    or_same_column_cleanup_sql,
    order_by_constant_cleanup_sql,
    recover_candidates_from_shape,
    union_wrapper_collapse_sql,
)


def test_recover_candidates_from_shape_recovers_constant_order_by_cleanup() -> None:
    sql = "SELECT id, name, email FROM users ORDER BY NULL"
    recovered = recover_candidates_from_shape("demo.user.orderByConstant", sql)

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "REMOVE_CONSTANT_ORDER_BY_RECOVERED"
    assert recovered[0]["rewrittenSql"] == "SELECT id, name, email FROM users"


def test_recover_candidates_from_shape_recovers_boolean_tautology_cleanup() -> None:
    sql = "SELECT id, name FROM users WHERE 1 = 1 ORDER BY created_at DESC"
    recovered = recover_candidates_from_shape("demo.user.booleanTautology", sql)

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED"
    assert recovered[0]["rewrittenSql"] == "SELECT id, name FROM users ORDER BY created_at DESC"


def test_order_by_constant_cleanup_sql_returns_none_for_real_ordering() -> None:
    sql = "SELECT id, name FROM users ORDER BY created_at DESC"
    assert order_by_constant_cleanup_sql(sql) is None


def test_boolean_tautology_cleanup_sql_removes_where_when_only_tautology_present() -> None:
    sql = "SELECT id, name FROM users WHERE 1 = 1"
    assert boolean_tautology_cleanup_sql(sql) == "SELECT id, name FROM users"


def test_recover_candidates_from_shape_recovers_single_value_in_list_cleanup() -> None:
    sql = "SELECT id, name FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC"
    recovered = recover_candidates_from_shape("demo.user.inList", sql)

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED"
    assert recovered[0]["rewrittenSql"] == "SELECT id, name FROM users WHERE status = 'ACTIVE' ORDER BY created_at DESC"


def test_in_list_single_value_cleanup_sql_rewrites_single_not_in_to_inequality() -> None:
    sql = "SELECT id, name FROM users WHERE status NOT IN ('ACTIVE')"
    assert in_list_single_value_cleanup_sql(sql) == "SELECT id, name FROM users WHERE status != 'ACTIVE'"


def test_recover_candidates_from_shape_recovers_or_same_column_cleanup() -> None:
    sql = "SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC"
    recovered = recover_candidates_from_shape("demo.user.orPair", sql)

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "SIMPLIFY_OR_TO_IN_RECOVERED"
    assert recovered[0]["rewrittenSql"] == (
        "SELECT id, name FROM users WHERE status IN ('ACTIVE', 'PENDING') ORDER BY created_at DESC"
    )


def test_case_when_true_cleanup_sql_simplifies_identity_case_expression() -> None:
    sql = "SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC"
    assert case_when_true_cleanup_sql(sql) == "SELECT id, status AS status FROM users ORDER BY created_at DESC"


def test_coalesce_identity_cleanup_sql_simplifies_identity_coalesce_expression() -> None:
    sql = "SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC"
    assert coalesce_identity_cleanup_sql(sql) == "SELECT id, status AS status FROM users ORDER BY created_at DESC"


def test_expression_folding_cleanup_sql_folds_constant_predicate_expression() -> None:
    sql = "SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC"
    assert expression_folding_cleanup_sql(sql) == "SELECT id, name FROM users WHERE id = 2 ORDER BY created_at DESC"


def test_limit_large_cleanup_sql_removes_oversized_limit_suffix() -> None:
    sql = "SELECT id, name FROM users ORDER BY created_at DESC LIMIT 1000000"
    assert limit_large_cleanup_sql(sql) == "SELECT id, name FROM users ORDER BY created_at DESC"


def test_null_comparison_cleanup_sql_normalizes_inequality_null_check() -> None:
    sql = "SELECT id, name FROM users WHERE email != NULL ORDER BY created_at DESC"
    assert null_comparison_cleanup_sql(sql) == "SELECT id, name FROM users WHERE email IS NOT NULL ORDER BY created_at DESC"


def test_distinct_on_cleanup_sql_simplifies_distinct_on_key_projection() -> None:
    sql = "SELECT DISTINCT ON (status) status FROM users ORDER BY status"
    assert distinct_on_cleanup_sql(sql) == "SELECT DISTINCT status FROM users ORDER BY status"


def test_exists_self_cleanup_sql_removes_self_identity_exists_filter() -> None:
    sql = "SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id) ORDER BY created_at DESC"
    assert exists_self_cleanup_sql(sql) == "SELECT id, name FROM users u ORDER BY created_at DESC"


def test_union_wrapper_collapse_sql_unwraps_static_union_wrapper() -> None:
    sql = (
        "SELECT id, status, shipped_at FROM ("
        "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
        "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'"
        ") su ORDER BY status, id"
    )
    assert union_wrapper_collapse_sql(sql) == (
        "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
        "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED' ORDER BY status, id"
    )
