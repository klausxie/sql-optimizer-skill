from __future__ import annotations

from pathlib import Path

from sqlopt.stages.validate_convergence import (
    BOOLEAN_TAUTOLOGY_SHAPE_FAMILY,
    CASE_WHEN_TRUE_SHAPE_FAMILY,
    COALESCE_IDENTITY_SHAPE_FAMILY,
    DISTINCT_ON_SHAPE_FAMILY,
    DISTINCT_ALIAS_SHAPE_FAMILY,
    DISTINCT_WRAPPER_SHAPE_FAMILY,
    EXPRESSION_FOLDING_SHAPE_FAMILY,
    EXISTS_SELF_SHAPE_FAMILY,
    GROUP_BY_ALIAS_SHAPE_FAMILY,
    GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY,
    GROUP_BY_WRAPPER_PATCH_FAMILY,
    IN_LIST_SINGLE_VALUE_SHAPE_FAMILY,
    LIMIT_LARGE_SHAPE_FAMILY,
    NULL_COMPARISON_SHAPE_FAMILY,
    OR_SAME_COLUMN_SHAPE_FAMILY,
    ORDER_BY_CONSTANT_SHAPE_FAMILY,
    SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES,
    SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES,
    SUPPORTED_STATIC_SHAPE_FAMILIES,
    HAVING_WRAPPER_PATCH_FAMILY,
    STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
    STATIC_CTE_PATCH_FAMILY,
    STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
    build_statement_convergence_row,
    infer_shape_family_from_sql_unit,
    patch_family_from_strategy_name,
)


def _sql_unit(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sqlKey": "demo.user.listUsers",
        "statementKey": "demo.user.listUsers",
        "statementType": "select",
        "sql": "SELECT id FROM users",
        "templateSql": "SELECT id FROM users",
        "dynamicFeatures": [],
    }
    payload.update(overrides)
    return payload


def _acceptance_row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sqlKey": "demo.user.listUsers",
        "statementKey": "demo.user.listUsers",
        "status": "PASS",
        "selectedCandidateId": "c1",
        "semanticEquivalence": {"status": "PASS"},
        "rewriteFacts": {
            "dynamicTemplate": {
                "capabilityProfile": {
                    "shapeFamily": "STATIC_STATEMENT",
                    "baselineFamily": "STATIC_STATEMENT_REWRITE",
                    "patchSurface": "statement",
                }
            }
        },
        "templateRewriteOps": [{"op": "replace_statement_body", "targetRef": "statement"}],
    }
    payload.update(overrides)
    return payload


def test_build_statement_convergence_row_keeps_union_blocked_boundary() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.shipment.union",
        rows=[
            _acceptance_row(
                sqlKey="demo.shipment.union",
                statementKey="demo.shipment.union",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.shipment.union",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_shipment_union/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.shipment.union",
            statementKey="demo.shipment.union",
            sql="SELECT status FROM shipments UNION SELECT status FROM orders",
        ),
        proposal={},
    )

    assert row["shapeFamily"] == "UNION"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "SHAPE_FAMILY_NOT_TARGET"


def test_build_statement_convergence_row_uses_strategy_family_hint_for_static_cte() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.cte",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.cte",
                statementKey="demo.user.cte",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.cte",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_cte/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.cte",
            statementKey="demo.user.cte",
            sql="WITH recent_users AS (SELECT id FROM users) SELECT id FROM recent_users",
            templateSql="WITH recent_users AS (SELECT id FROM users) SELECT id FROM recent_users",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "INLINE_CTE"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_STATEMENT"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_CTE_PATCH_FAMILY


def test_build_statement_convergence_row_uses_static_wrapper_family_for_simple_subquery_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.shipment.wrapper",
        rows=[
            _acceptance_row(
                sqlKey="demo.shipment.wrapper",
                statementKey="demo.shipment.wrapper",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.shipment.wrapper",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_shipment_wrapper/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.shipment.wrapper",
            statementKey="demo.shipment.wrapper",
            sql="SELECT id, status FROM (SELECT id, status FROM shipments) s ORDER BY id",
            templateSql="SELECT id, status FROM (SELECT id, status FROM shipments) s ORDER BY id",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "INLINE_SUBQUERY"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_SUBQUERY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_uses_static_alias_projection_family_for_alias_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.alias",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.alias",
                statementKey="demo.user.alias",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.alias",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_alias/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.alias",
            statementKey="demo.user.alias",
            sql="SELECT id AS id, name AS name FROM users ORDER BY created_at DESC",
            templateSql="SELECT id AS id, name AS name FROM users ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_ALIAS_PROJECTION"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_ALIAS_PROJECTION_PATCH_FAMILY


def test_build_statement_convergence_row_uses_group_by_wrapper_family_for_safe_wrapper_collapse() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.order.groupby.wrapper",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.groupby.wrapper",
                statementKey="demo.order.groupby.wrapper",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.order.groupby.wrapper",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_groupby_wrapper/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.order.groupby.wrapper",
            statementKey="demo.order.groupby.wrapper",
            sql=(
                "SELECT status, order_count FROM ("
                "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status"
                ") grouped_status ORDER BY status"
            ),
            templateSql=(
                "SELECT status, order_count FROM ("
                "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status"
                ") grouped_status ORDER BY status"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == "GROUP_BY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == GROUP_BY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_uses_having_wrapper_family_for_safe_wrapper_collapse() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.order.having.wrapper",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.having.wrapper",
                statementKey="demo.order.having.wrapper",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.order.having.wrapper",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_having_wrapper/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.order.having.wrapper",
            statementKey="demo.order.having.wrapper",
            sql=(
                "SELECT user_id, COUNT(*) AS total FROM ("
                "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1"
                ") oh ORDER BY user_id"
            ),
            templateSql=(
                "SELECT user_id, COUNT(*) AS total FROM ("
                "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1"
                ") oh ORDER BY user_id"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == "HAVING_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == HAVING_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_uses_distinct_on_family_for_semantic_preserving_candidate() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.distinct_on",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.distinct_on",
                statementKey="demo.user.distinct_on",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.distinct_on",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_distinct_on/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.distinct_on",
            statementKey="demo.user.distinct_on",
            sql="SELECT DISTINCT ON (status) status FROM users ORDER BY status",
            templateSql="SELECT DISTINCT ON (status) status FROM users ORDER BY status",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SEMANTIC_PRESERVING"}],
        },
    )

    assert row["shapeFamily"] == DISTINCT_ON_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_DISTINCT_ON_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_exists_family_for_redundant_subquery_removal() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.exists_self",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.exists_self",
                statementKey="demo.user.exists_self",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.exists_self",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_exists_self/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.exists_self",
            statementKey="demo.user.exists_self",
            sql="SELECT id FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id)",
            templateSql="SELECT id FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id)",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REDUNDANT_SUBQUERY_REMOVAL"}],
        },
    )

    assert row["shapeFamily"] == EXISTS_SELF_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_EXISTS_REWRITE"


def test_build_statement_convergence_row_uses_union_wrapper_family_for_wrapper_removal() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.shipment.union_wrapper",
        rows=[
            _acceptance_row(
                sqlKey="demo.shipment.union_wrapper",
                statementKey="demo.shipment.union_wrapper",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.shipment.union_wrapper",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_shipment_union_wrapper/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.shipment.union_wrapper",
            statementKey="demo.shipment.union_wrapper",
            sql=(
                "SELECT id, status FROM ("
                "SELECT id, status FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status FROM shipments WHERE status = 'DELIVERED'"
                ") su ORDER BY status"
            ),
            templateSql=(
                "SELECT id, status FROM ("
                "SELECT id, status FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status FROM shipments WHERE status = 'DELIVERED'"
                ") su ORDER BY status"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "Remove redundant subquery wrapper"}],
        },
    )

    assert row["shapeFamily"] == "UNION_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_UNION_COLLAPSE"


def test_build_statement_convergence_row_uses_group_by_having_alias_shape_for_alias_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.order.groupby.having.alias",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.groupby.having.alias",
                statementKey="demo.order.groupby.having.alias",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.order.groupby.having.alias",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_groupby_having_alias/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.order.groupby.having.alias",
            statementKey="demo.order.groupby.having.alias",
            sql=(
                "SELECT o.user_id AS user_id, COUNT(*) AS total "
                "FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id"
            ),
            templateSql=(
                "SELECT o.user_id AS user_id, COUNT(*) AS total "
                "FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"


def test_build_statement_convergence_row_uses_group_by_alias_shape_for_alias_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.order.groupby.alias",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.groupby.alias",
                statementKey="demo.order.groupby.alias",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.order.groupby.alias",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_groupby_alias/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.order.groupby.alias",
            statementKey="demo.order.groupby.alias",
            sql=(
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount "
                "FROM orders o GROUP BY o.status ORDER BY o.status"
            ),
            templateSql=(
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount "
                "FROM orders o GROUP BY o.status ORDER BY o.status"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == GROUP_BY_ALIAS_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "GROUP_BY_FROM_ALIAS_CLEANUP"


def test_build_statement_convergence_row_uses_distinct_wrapper_shape_for_safe_wrapper_collapse() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.distinct.wrapper",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.distinct.wrapper",
                statementKey="demo.user.distinct.wrapper",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.distinct.wrapper",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_distinct_wrapper/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.distinct.wrapper",
            statementKey="demo.user.distinct.wrapper",
            sql=(
                "SELECT DISTINCT status FROM ("
                "SELECT DISTINCT status FROM users"
                ") ds ORDER BY status"
            ),
            templateSql=(
                "SELECT DISTINCT status FROM ("
                "SELECT DISTINCT status FROM users"
                ") ds ORDER BY status"
            ),
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == DISTINCT_WRAPPER_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "REDUNDANT_DISTINCT_WRAPPER"


def test_build_statement_convergence_row_uses_distinct_alias_shape_for_alias_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.distinct.alias",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.distinct.alias",
                statementKey="demo.user.distinct.alias",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.distinct.alias",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_distinct_alias/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.distinct.alias",
            statementKey="demo.user.distinct.alias",
            sql="SELECT DISTINCT u.status FROM users u ORDER BY u.status",
            templateSql="SELECT DISTINCT u.status FROM users u ORDER BY u.status",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == DISTINCT_ALIAS_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "DISTINCT_FROM_ALIAS_CLEANUP"


def test_build_statement_convergence_row_uses_order_by_constant_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.orderby.constant",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.orderby.constant",
                statementKey="demo.user.orderby.constant",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.orderby.constant",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_orderby_constant/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.orderby.constant",
            statementKey="demo.user.orderby.constant",
            sql="SELECT id, name, email FROM users ORDER BY NULL",
            templateSql="SELECT id, name, email FROM users ORDER BY NULL",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_CONSTANT_ORDER_BY_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_CONSTANT_ORDER_BY_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == ORDER_BY_CONSTANT_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_ORDER_BY_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_boolean_tautology_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.boolean.tautology",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.boolean.tautology",
                statementKey="demo.user.boolean.tautology",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.boolean.tautology",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_boolean_tautology/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.boolean.tautology",
            statementKey="demo.user.boolean.tautology",
            sql="SELECT id, name, email, status FROM users WHERE 1 = 1 ORDER BY created_at DESC",
            templateSql="SELECT id, name, email, status FROM users WHERE 1 = 1 ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == BOOLEAN_TAUTOLOGY_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_BOOLEAN_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_in_list_single_value_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.in.list.single",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.in.list.single",
                statementKey="demo.user.in.list.single",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.in.list.single",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_in_list_single/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.in.list.single",
            statementKey="demo.user.in.list.single",
            sql="SELECT id, name, email, status FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC",
            templateSql="SELECT id, name, email, status FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == IN_LIST_SINGLE_VALUE_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_IN_LIST_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_or_same_column_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.or.same.column",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.or.same.column",
                statementKey="demo.user.or.same.column",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.or.same.column",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_or_same_column/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.or.same.column",
            statementKey="demo.user.or.same.column",
            sql="SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "SIMPLIFY_OR_TO_IN_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SIMPLIFY_OR_TO_IN_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == OR_SAME_COLUMN_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_OR_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_case_when_true_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.case.when.true",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.case.when.true",
                statementKey="demo.user.case.when.true",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.case.when.true",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_case_when_true/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.case.when.true",
            statementKey="demo.user.case.when.true",
            sql="SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC",
            templateSql="SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == CASE_WHEN_TRUE_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_CASE_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_coalesce_identity_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.coalesce.identity",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.coalesce.identity",
                statementKey="demo.user.coalesce.identity",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.coalesce.identity",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_coalesce_identity/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.coalesce.identity",
            statementKey="demo.user.coalesce.identity",
            sql="SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC",
            templateSql="SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "SIMPLIFY_COALESCE_IDENTITY_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SIMPLIFY_COALESCE_IDENTITY_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == COALESCE_IDENTITY_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_COALESCE_SIMPLIFICATION"


def test_build_statement_convergence_row_uses_expression_folding_shape_for_cleanup() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.expression.folding",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.expression.folding",
                statementKey="demo.user.expression.folding",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.expression.folding",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_expression_folding/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.expression.folding",
            statementKey="demo.user.expression.folding",
            sql="SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC",
        ),
        proposal={
            "candidateGenerationDiagnostics": {"recoveryStrategy": "FOLD_CONSTANT_EXPRESSION_RECOVERED"},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "FOLD_CONSTANT_EXPRESSION_RECOVERED"}],
        },
    )

    assert row["shapeFamily"] == EXPRESSION_FOLDING_SHAPE_FAMILY
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_EXPRESSION_FOLDING"


def test_static_family_registries_cover_current_convergence_abstractions() -> None:
    assert "STATIC_INCLUDE_ONLY" in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert "STATIC_SUBQUERY_WRAPPER" in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert DISTINCT_WRAPPER_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert DISTINCT_ALIAS_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert ORDER_BY_CONSTANT_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert BOOLEAN_TAUTOLOGY_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert IN_LIST_SINGLE_VALUE_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert OR_SAME_COLUMN_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert CASE_WHEN_TRUE_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert COALESCE_IDENTITY_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert EXPRESSION_FOLDING_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert LIMIT_LARGE_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert NULL_COMPARISON_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert DISTINCT_ON_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert EXISTS_SELF_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert "UNION_WRAPPER" in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert "GROUP_BY_WRAPPER" in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert GROUP_BY_ALIAS_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
    assert SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES[("GROUP_BY_WRAPPER", "DYNAMIC_FILTER_WRAPPER_COLLAPSE")] == GROUP_BY_WRAPPER_PATCH_FAMILY
    assert SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES[("HAVING_WRAPPER", "DYNAMIC_FILTER_WRAPPER_COLLAPSE")] == HAVING_WRAPPER_PATCH_FAMILY
    assert SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES["HAVING_WRAPPER"]["REMOVE_REDUNDANT_SUBQUERY_RECOVERED"] == HAVING_WRAPPER_PATCH_FAMILY


def test_infer_shape_family_and_strategy_mapping_cover_current_small_abstractions() -> None:
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            dynamicFeatures=["INCLUDE"],
            templateSql="<include refid=\"BaseColumns\"/>",
        )
    ) == "STATIC_INCLUDE_ONLY"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT order_no, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn FROM orders",
            templateSql="SELECT order_no, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn FROM orders",
        )
    ) == "WINDOW"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, status FROM (SELECT id, status FROM shipments) s ORDER BY id",
            templateSql="SELECT id, status FROM (SELECT id, status FROM shipments) s ORDER BY id",
        )
    ) == "STATIC_SUBQUERY_WRAPPER"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT status, order_count FROM ("
                "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status"
                ") grouped_status ORDER BY status"
            ),
            templateSql=(
                "SELECT status, order_count FROM ("
                "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status"
                ") grouped_status ORDER BY status"
            ),
        )
    ) == "GROUP_BY_WRAPPER"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT user_id, COUNT(*) AS total FROM ("
                "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1"
                ") oh ORDER BY user_id"
            ),
            templateSql=(
                "SELECT user_id, COUNT(*) AS total FROM ("
                "SELECT user_id, COUNT(*) AS total FROM orders GROUP BY user_id HAVING COUNT(*) > 1"
                ") oh ORDER BY user_id"
            ),
        )
    ) == "HAVING_WRAPPER"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name, email FROM users ORDER BY NULL",
            templateSql="SELECT id, name, email FROM users ORDER BY NULL",
        )
    ) == ORDER_BY_CONSTANT_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users WHERE status = 'ACTIVE' OR status = 'PENDING' ORDER BY created_at DESC",
        )
    ) == OR_SAME_COLUMN_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC",
            templateSql="SELECT id, CASE WHEN TRUE THEN status ELSE status END AS status FROM users ORDER BY created_at DESC",
        )
    ) == CASE_WHEN_TRUE_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC",
            templateSql="SELECT id, COALESCE(status, status) AS status FROM users ORDER BY created_at DESC",
        )
    ) == COALESCE_IDENTITY_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users WHERE id = 1 + 1 ORDER BY created_at DESC",
        )
    ) == EXPRESSION_FOLDING_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users ORDER BY created_at DESC LIMIT 1000000",
            templateSql="SELECT id, name FROM users ORDER BY created_at DESC LIMIT 1000000",
        )
    ) == LIMIT_LARGE_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users WHERE email != NULL ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users WHERE email != NULL ORDER BY created_at DESC",
        )
    ) == NULL_COMPARISON_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT DISTINCT ON (status) status FROM users ORDER BY status",
            templateSql="SELECT DISTINCT ON (status) status FROM users ORDER BY status",
        )
    ) == DISTINCT_ON_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id) ORDER BY created_at DESC",
            templateSql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM users u2 WHERE u2.id = u.id) ORDER BY created_at DESC",
        )
    ) == EXISTS_SELF_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT id, status, shipped_at FROM ("
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'"
                ") su ORDER BY status, id"
            ),
            templateSql=(
                "SELECT id, status, shipped_at FROM ("
                "SELECT id, status, shipped_at FROM shipments WHERE status = 'SHIPPED' "
                "UNION SELECT id, status, shipped_at FROM shipments WHERE status = 'DELIVERED'"
                ") su ORDER BY status, id"
            ),
        )
    ) == "UNION_WRAPPER"
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name, email, status FROM users WHERE 1 = 1 ORDER BY created_at DESC",
            templateSql="SELECT id, name, email, status FROM users WHERE 1 = 1 ORDER BY created_at DESC",
        )
    ) == BOOLEAN_TAUTOLOGY_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name, email, status FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC",
            templateSql="SELECT id, name, email, status FROM users WHERE status IN ('ACTIVE') ORDER BY created_at DESC",
        )
    ) == IN_LIST_SINGLE_VALUE_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT DISTINCT status FROM ("
                "SELECT DISTINCT status FROM users"
                ") ds ORDER BY status"
            ),
            templateSql=(
                "SELECT DISTINCT status FROM ("
                "SELECT DISTINCT status FROM users"
                ") ds ORDER BY status"
            ),
        )
    ) == DISTINCT_WRAPPER_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT DISTINCT u.status FROM users u ORDER BY u.status",
            templateSql="SELECT DISTINCT u.status FROM users u ORDER BY u.status",
        )
    ) == DISTINCT_ALIAS_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount "
                "FROM orders o GROUP BY o.status ORDER BY o.status"
            ),
            templateSql=(
                "SELECT o.status AS status, COUNT(*) AS total, SUM(o.amount) AS total_amount "
                "FROM orders o GROUP BY o.status ORDER BY o.status"
            ),
        )
    ) == GROUP_BY_ALIAS_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT o.user_id AS user_id, COUNT(*) AS total "
                "FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id"
            ),
            templateSql=(
                "SELECT o.user_id AS user_id, COUNT(*) AS total "
                "FROM orders o GROUP BY o.user_id HAVING COUNT(*) > 1 ORDER BY o.user_id"
            ),
        )
    ) == GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY
    assert infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id AS id, name AS name FROM users ORDER BY created_at DESC",
            templateSql="SELECT id AS id, name AS name FROM users ORDER BY created_at DESC",
        )
    ) == "STATIC_ALIAS_PROJECTION"
    assert patch_family_from_strategy_name("remove-redundant-group-by-from-alias-recovered") == "GROUP_BY_FROM_ALIAS_CLEANUP"
    assert patch_family_from_strategy_name("REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED") == "REDUNDANT_DISTINCT_WRAPPER"
    assert patch_family_from_strategy_name("REMOVE_CONSTANT_ORDER_BY_RECOVERED") == "STATIC_ORDER_BY_SIMPLIFICATION"
    assert patch_family_from_strategy_name("REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED") == "STATIC_BOOLEAN_SIMPLIFICATION"
    assert patch_family_from_strategy_name("REMOVE_TAUTOLOGY") == "STATIC_BOOLEAN_SIMPLIFICATION"
    assert patch_family_from_strategy_name("simplify-single-value-in-clause") == "STATIC_IN_LIST_SIMPLIFICATION"
    assert patch_family_from_strategy_name("SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED") == "STATIC_IN_LIST_SIMPLIFICATION"
    assert patch_family_from_strategy_name("SIMPLIFY_OR_TO_IN_RECOVERED") == "STATIC_OR_SIMPLIFICATION"
    assert patch_family_from_strategy_name("SIMPLIFY_CASE_WHEN_TRUE_RECOVERED") == "STATIC_CASE_SIMPLIFICATION"
    assert patch_family_from_strategy_name("SIMPLIFY_COALESCE_IDENTITY_RECOVERED") == "STATIC_COALESCE_SIMPLIFICATION"
    assert patch_family_from_strategy_name("FOLD_CONSTANT_EXPRESSION_RECOVERED") == "STATIC_EXPRESSION_FOLDING"
    assert patch_family_from_strategy_name("FOLDED_EXPRESSION_SIMPLIFY") == "STATIC_EXPRESSION_FOLDING"
    assert patch_family_from_strategy_name("SIMPLIFY_EXPRESSION") == "STATIC_EXPRESSION_FOLDING"
    assert patch_family_from_strategy_name("REMOVE_LARGE_LIMIT_RECOVERED") == "STATIC_LIMIT_OPTIMIZATION"
    assert patch_family_from_strategy_name("SIMPLIFY_NULL_COMPARISON_RECOVERED") == "STATIC_NULL_COMPARISON"
    assert patch_family_from_strategy_name("SIMPLIFY_DISTINCT_ON_RECOVERED") == "STATIC_DISTINCT_ON_SIMPLIFICATION"
    assert patch_family_from_strategy_name("SAFE_EXISTS_REWRITE") == "STATIC_EXISTS_REWRITE"
    assert patch_family_from_strategy_name("SAFE_UNION_COLLAPSE") == "STATIC_UNION_COLLAPSE"
    assert patch_family_from_strategy_name("REMOVE_INVALID_ORDER_BY") == "STATIC_ORDER_BY_SIMPLIFICATION"
    assert patch_family_from_strategy_name("REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED") == HAVING_WRAPPER_PATCH_FAMILY
    assert patch_family_from_strategy_name("REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED") == "DISTINCT_FROM_ALIAS_CLEANUP"
