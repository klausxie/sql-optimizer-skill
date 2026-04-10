from __future__ import annotations

from sqlopt.platforms.sql.candidate_generation_support import (
    boolean_tautology_cleanup_sql,
    case_when_true_cleanup_sql,
    classify_supported_choose_guarded_filter_candidate,
    coalesce_identity_cleanup_sql,
    distinct_on_cleanup_sql,
    expression_folding_cleanup_sql,
    exists_self_cleanup_sql,
    is_observed_in_subquery_rewrite_strategy,
    is_supported_choose_guarded_filter,
    in_list_single_value_cleanup_sql,
    limit_large_cleanup_sql,
    normalize_strategy_text,
    null_comparison_cleanup_sql,
    or_same_column_cleanup_sql,
    order_by_constant_cleanup_sql,
    recover_candidates_from_shape,
    union_wrapper_collapse_sql,
)
from sqlopt.platforms.sql.rewrite_facts import safe_baseline_recovery_family


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


def test_normalize_strategy_text_collapses_observed_wording_variants() -> None:
    assert normalize_strategy_text("in-to-exists") == "in_to_exists"
    assert normalize_strategy_text("IN SUBQUERY TO JOIN") == "in_subquery_to_join"


def test_is_observed_in_subquery_rewrite_strategy_matches_only_known_variants() -> None:
    assert is_observed_in_subquery_rewrite_strategy("in-to-exists") is True
    assert is_observed_in_subquery_rewrite_strategy("in_subquery_to_join") is True
    assert is_observed_in_subquery_rewrite_strategy("subquery_to_exists") is True
    assert is_observed_in_subquery_rewrite_strategy("subquery_to_join") is True
    assert is_observed_in_subquery_rewrite_strategy("exists_transform") is True
    assert is_observed_in_subquery_rewrite_strategy("index_optimization") is False


def test_is_supported_choose_guarded_filter_rejects_outer_if_with_ordering_clauses() -> None:
    sql_unit = {
        "dynamicFeatures": ["CHOOSE", "IF"],
        "templateSql": (
            "SELECT id, name FROM users <where><choose>"
            "<when test=\"status != null\">status = #{status}</when>"
            "<otherwise>1 = 1</otherwise>"
            "</choose></where> "
            "<if test=\"sortByCreated\">ORDER BY created_at DESC LIMIT #{limit}</if>"
        ),
    }

    assert is_supported_choose_guarded_filter(sql_unit) is False


def test_is_supported_choose_guarded_filter_rejects_bare_top_level_choose() -> None:
    sql_unit = {
        "dynamicFeatures": ["CHOOSE"],
        "templateSql": (
            "SELECT id, name FROM users <choose>"
            "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
            "<otherwise>WHERE 1 = 1</otherwise>"
            "</choose>"
        ),
    }

    assert is_supported_choose_guarded_filter(sql_unit) is False


def test_is_supported_choose_guarded_filter_accepts_where_wrapped_choose_filter() -> None:
    sql_unit = {
        "dynamicFeatures": ["CHOOSE", "WHERE"],
        "templateSql": (
            "SELECT id, name FROM users <where><choose>"
            "<when test=\"status != null\">status = #{status}</when>"
            "<otherwise>1 = 1</otherwise>"
            "</choose></where>"
        ),
    }

    assert is_supported_choose_guarded_filter(sql_unit) is True


def test_classify_supported_choose_guarded_filter_candidate_distinguishes_keyword_pool_entries() -> None:
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
    }

    semantic_risk = classify_supported_choose_guarded_filter_candidate(
        original_sql=original_sql,
        sql_unit=sql_unit,
        candidate={
            "id": "opt-001",
            "rewriteStrategy": "union_or_elimination",
            "rewrittenSql": (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users AS u WHERE (name ILIKE #{keywordPattern} OR status = #{status}) "
                "AND status != 'DELETED' ORDER BY created_at DESC"
            ),
        },
    )
    no_safe_baseline = classify_supported_choose_guarded_filter_candidate(
        original_sql=original_sql,
        sql_unit=sql_unit,
        candidate={
            "id": "opt-002",
            "rewriteStrategy": "redundant_condition_removal",
            "rewrittenSql": (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users AS u WHERE name ILIKE #{keywordPattern} ORDER BY created_at DESC"
            ),
        },
    )
    unsupported = classify_supported_choose_guarded_filter_candidate(
        original_sql=original_sql,
        sql_unit=sql_unit,
        candidate={
            "id": "opt-003",
            "rewriteStrategy": "index_driven_union",
            "rewrittenSql": (
                "SELECT id, name, email, status, created_at, updated_at "
                "FROM users AS u WHERE name ILIKE #{keywordPattern} ORDER BY created_at DESC"
            ),
        },
    )

    assert semantic_risk == (
        "SEMANTIC_RISK_REWRITE",
        "candidate merges choose branches on a supported choose-guarded filter without a template-preserving safe path",
    )
    assert no_safe_baseline == (
        "NO_SAFE_BASELINE_MATCH",
        "candidate rewrites choose-guarded filter predicates but does not match any supported template-preserving baseline",
    )
    assert unsupported == (
        "UNSUPPORTED_STRATEGY",
        "candidate uses an unsupported union/index strategy on a supported choose-guarded filter",
    )


def test_recover_candidates_from_shape_recovers_static_statement_rewrite_for_plain_select() -> None:
    sql = "SELECT id, name, email, status, created_at FROM users"
    recovered = recover_candidates_from_shape(
        "demo.test.complex.staticSimpleSelect",
        sql,
        {"sqlKey": "demo.test.complex.staticSimpleSelect", "dynamicFeatures": [], "templateSql": sql},
    )

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "INLINE_SUBQUERY"
    assert recovered[0]["rewrittenSql"] == sql


def test_recover_candidates_from_shape_recovers_static_include_wrapper_collapse() -> None:
    sql = "SELECT id, name, email, status, created_at FROM users"
    recovered = recover_candidates_from_shape(
        "demo.test.complex.includeSimple",
        sql,
        {
            "sqlKey": "demo.test.complex.includeSimple",
            "dynamicFeatures": ["INCLUDE"],
            "templateSql": "SELECT <include refid=\"BaseColumns\" /> FROM users",
        },
    )

    assert recovered
    assert recovered[0]["rewriteStrategy"] == "INLINE_SUBQUERY"
    assert recovered[0]["rewrittenSql"] == sql


def test_safe_baseline_recovery_family_recognizes_existing_if_guarded_filter_alias_cleanup_family() -> None:
    sql_unit = {
        "sqlKey": "demo.user.aliasCleanup",
        "sql": (
            "SELECT id AS id, name AS name FROM users "
            "WHERE status = #{status} ORDER BY created_at DESC"
        ),
        "templateSql": (
            "SELECT id AS id, name AS name FROM users "
            "<where><if test=\"status != null\">status = #{status}</if></where> "
            "ORDER BY created_at DESC"
        ),
        "dynamicFeatures": ["WHERE", "IF"],
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) == "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"


def test_safe_baseline_recovery_family_keeps_choose_guarded_filter_unmapped() -> None:
    sql_unit = {
        "sqlKey": "demo.user.advanced.findUsersByKeyword",
        "statementKey": "demo.user.advanced.findUsersByKeyword",
        "sql": (
            "SELECT id, name, email, status, created_at, updated_at FROM users "
            "WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') "
            "ORDER BY created_at DESC"
        ),
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
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) is None


def test_safe_baseline_recovery_family_recognizes_choose_local_cleanup_when_original_sql_matches_single_branch() -> None:
    sql_unit = {
        "sqlKey": "demo.user.advanced.findUsersByKeyword",
        "statementKey": "demo.user.advanced.findUsersByKeyword",
        "sql": (
            "SELECT id, name, email, status, created_at, updated_at FROM users "
            "WHERE upper(name) ILIKE upper(#{keyword})"
        ),
        "templateSql": (
            "SELECT id, name, email, status, created_at, updated_at FROM users "
            "<where><choose>"
            "<when test=\"keyword != null and keyword != ''\">upper(name) ILIKE upper(#{keyword})</when>"
            "<otherwise>status = 'ACTIVE'</otherwise>"
            "</choose></where>"
        ),
        "dynamicFeatures": ["WHERE", "CHOOSE"],
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) == "DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP"


def test_safe_baseline_recovery_family_recognizes_choose_local_cleanup_from_dynamic_render_identity() -> None:
    sql_unit = {
        "sqlKey": "demo.user.advanced.findUsersByKeyword",
        "statementKey": "demo.user.advanced.findUsersByKeyword",
        "sql": (
            "SELECT id, name, email, status, created_at, updated_at FROM users "
            "WHERE (name ILIKE #{keywordPattern} OR status = #{status} OR status != 'DELETED') "
            "ORDER BY created_at DESC"
        ),
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
        "dynamicRenderIdentity": {
            "surfaceType": "CHOOSE_BRANCH_BODY",
            "renderMode": "CHOOSE_BRANCH_RENDERED",
            "chooseOrdinal": 0,
            "branchOrdinal": 0,
            "branchKind": "WHEN",
            "branchTestFingerprint": "keyword != null and keyword != ''",
            "renderedBranchSql": "name ILIKE #{keywordPattern}",
            "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
            "requiredSiblingShape": {"branchCount": 3},
        },
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) == "DYNAMIC_CHOOSE_BRANCH_LOCAL_CLEANUP"


def test_safe_baseline_recovery_family_keeps_find_shipments_as_no_safe_baseline_sentinel() -> None:
    sql_unit = {
        "sqlKey": "demo.shipment.harness.findShipments",
        "sql": (
            "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments "
            "WHERE status = #{status} AND carrier = #{carrier} ORDER BY shipped_at DESC"
        ),
        "templateSql": (
            "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments "
            "<where><if test=\"status != null and status != ''\">AND status = #{status}</if>"
            "<if test=\"carrier != null and carrier != ''\">AND carrier = #{carrier}</if></where> "
            "ORDER BY shipped_at DESC"
        ),
        "dynamicFeatures": ["INCLUDE", "WHERE", "IF"],
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) is None


def test_safe_baseline_recovery_family_keeps_plain_foreach_include_boundaries_unmapped() -> None:
    sql_unit = {
        "sqlKey": "demo.shipment.harness.findShipmentsByOrderIds",
        "sql": "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments WHERE #{orderId}",
        "templateSql": (
            "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments "
            "<where><foreach collection=\"orderIds\" item=\"orderId\" open=\"order_id IN (\" separator=\",\" close=\")\">"
            "#{orderId}</foreach></where>"
        ),
        "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) is None


def test_safe_baseline_recovery_family_keeps_mixed_collection_predicate_unmapped() -> None:
    sql_unit = {
        "sqlKey": "demo.order.harness.findOrdersByUserIdsAndStatus",
        "sql": (
            "SELECT id, user_id, order_no, amount, status, created_at "
            "FROM orders WHERE user_id IN (#{userId}) AND status = #{status}"
        ),
        "templateSql": (
            "SELECT <include refid=\"OrderColumns\" /> FROM orders <where>"
            "<foreach collection=\"userIds\" item=\"userId\" open=\"user_id IN (\" separator=\",\" close=\")\">"
            "#{userId}</foreach>"
            "<if test=\"status != null and status != ''\">AND status = #{status}</if>"
            "</where>"
        ),
        "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH", "IF"],
    }

    assert safe_baseline_recovery_family(sql_unit, str(sql_unit["sql"])) is None
