from __future__ import annotations

from pathlib import Path

from sqlopt.devtools.sample_project_family_scopes import (
    GENERALIZATION_BATCH5_SQL_KEYS,
    GENERALIZATION_BATCH6_SQL_KEYS,
)
from sqlopt.stages.convergence_registry import (
    SAFE_BASELINE_SUBTYPE_POLICIES,
    SEMANTIC_RISK_TAIL_SQL_KEYS,
    UNSUPPORTED_STRATEGY_TAIL_SQL_KEYS,
)
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
    MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY,
    NULL_COMPARISON_SHAPE_FAMILY,
    OR_SAME_COLUMN_SHAPE_FAMILY,
    ORDER_BY_CONSTANT_SHAPE_FAMILY,
    SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES,
    SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES,
    SUPPORTED_STATIC_SHAPE_FAMILIES,
    HAVING_WRAPPER_PATCH_FAMILY,
    STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
    STATIC_CTE_PATCH_FAMILY,
    STATIC_INCLUDE_PATCH_FAMILY,
    STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
    build_statement_convergence_row,
    infer_shape_family_from_sql_unit,
    no_candidate_conflict_reason,
    not_target_boundary_bucket,
    not_target_boundary_pattern,
    patch_family_from_strategy_name,
    semantic_conflict_reason,
    validate_status_conflict_reason,
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


def _batch6_row(
    *,
    sql_key: str,
    sql: str,
    template_sql: str | None = None,
    dynamic_features: list[str] | None = None,
    selected_candidate_id: str | None = None,
    semantic_status: str = "PASS",
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    row = _acceptance_row(
        sqlKey=sql_key,
        statementKey=sql_key,
        selectedCandidateId=selected_candidate_id,
        rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
    )
    if semantic_status != "PASS":
        row["semanticEquivalence"] = {
            "status": semantic_status,
            "checks": {},
            "reasons": [],
            "hardConflicts": [],
        }

    sql_unit = _sql_unit(
        sqlKey=sql_key,
        statementKey=sql_key,
        sql=sql,
        templateSql=template_sql or sql,
        dynamicFeatures=dynamic_features or [],
    )
    proposal = {"candidateGenerationDiagnostics": {}, "llmCandidates": []}
    return sql_unit, [row], proposal


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


def test_no_candidate_conflict_reason_distinguishes_missing_safe_baseline() -> None:
    assert (
        no_candidate_conflict_reason(
            {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "EMPTY_CANDIDATES",
                    "recoveryReason": "NO_SAFE_BASELINE_SHAPE_MATCH",
                    "rawCandidateCount": 0,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            }
        )
        == "NO_SAFE_BASELINE_RECOVERY"
    )


def test_no_candidate_conflict_reason_distinguishes_group_by_safe_baseline() -> None:
    assert (
        no_candidate_conflict_reason(
            {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "EMPTY_CANDIDATES",
                    "recoveryReason": "NO_SAFE_BASELINE_GROUP_BY",
                    "rawCandidateCount": 0,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            }
        )
        == "NO_SAFE_BASELINE_RECOVERY"
    )


def test_no_candidate_conflict_reason_distinguishes_low_value_only_candidates() -> None:
    assert (
        no_candidate_conflict_reason(
            {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 2,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            }
        )
        == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY"
    )


def test_no_candidate_conflict_reason_preserves_explicit_unsupported_strategy_tail() -> None:
    assert (
        no_candidate_conflict_reason(
            {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "EMPTY_CANDIDATES",
                    "recoveryReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY",
                    "rawCandidateCount": 0,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            }
        )
        == "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY"
    )


def test_build_statement_convergence_row_clarifies_canonical_noop_low_value_tail() -> None:
    sql_unit, rows, proposal = _batch6_row(
        sql_key="demo.test.complex.staticSimpleSelect",
        sql="SELECT id, name FROM users",
        template_sql="SELECT id, name FROM users",
    )
    proposal.update(
        {
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 1,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "lowValueAssessments": [
                    {
                        "candidateId": "covering_index_1",
                        "category": "CANONICAL_NOOP_HINT",
                    }
                ],
            }
        }
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.staticSimpleSelect",
        rows=rows,
        sql_key="demo.test.complex.staticSimpleSelect",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_staticSimpleSelect/index.json"),
        sql_unit=sql_unit,
        proposal=proposal,
    )

    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_CANONICAL_NOOP_HINT"


def test_convergence_registry_keeps_semantic_and_unsupported_tails_explicit() -> None:
    assert "demo.test.complex.existsSubquery" in SEMANTIC_RISK_TAIL_SQL_KEYS
    assert "demo.test.complex.leftJoinWithNull" in SEMANTIC_RISK_TAIL_SQL_KEYS
    assert "demo.test.complex.fragmentMultiplePlaces" in SEMANTIC_RISK_TAIL_SQL_KEYS
    assert "demo.test.complex.chooseBasic" in SEMANTIC_RISK_TAIL_SQL_KEYS
    assert "demo.test.complex.chooseWithLimit" in UNSUPPORTED_STRATEGY_TAIL_SQL_KEYS


def test_safe_baseline_subtype_policies_freeze_and_defer_current_lanes() -> None:
    expected_dispositions = {
        "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER": "defer",
        "NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE": "defer",
        "NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY": "freeze",
        "NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE": "freeze",
        "NO_SAFE_BASELINE_FOREACH_INCLUDE_PREDICATE": "defer",
        "NO_SAFE_BASELINE_GROUP_BY": "freeze",
    }
    assert {
        key: str((policy or {}).get("disposition") or "")
        for key, policy in SAFE_BASELINE_SUBTYPE_POLICIES.items()
    } == expected_dispositions


def test_choose_capability_guardrail_truth_stays_split_between_primary_and_non_goals() -> None:
    primary_row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.advanced.findUsersByKeyword",
            statementKey="demo.user.advanced.findUsersByKeyword",
            sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
            templateSql=(
                "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
                "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
                "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
                "<when test=\"status != null and status != ''\">status = #{status}</when>"
                "<otherwise>status != 'DELETED'</otherwise>"
                "</choose></where> ORDER BY created_at DESC"
            ),
            dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
        ),
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER",
                "rawCandidateCount": 3,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "SEMANTIC_RISK_REWRITE"},
                    {"candidateId": "opt-002", "category": "NO_SAFE_BASELINE_MATCH"},
                    {"candidateId": "opt-003", "category": "UNSUPPORTED_STRATEGY"},
                ],
            },
        },
    )

    choose_basic_sql_unit = _sql_unit(
        sqlKey="demo.test.complex.chooseBasic",
        statementKey="demo.test.complex.chooseBasic",
        sql="SELECT id, name, status FROM users WHERE status = 'active'",
        templateSql=(
            "SELECT id, name, status FROM users <choose>"
            "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
            "<when test=\"type == 'inactive'\">WHERE status = 'inactive'</when>"
            "<otherwise>WHERE 1=1</otherwise>"
            "</choose>"
        ),
        dynamicFeatures=["CHOOSE"],
    )

    choose_limit_sql_unit = _sql_unit(
        sqlKey="demo.test.complex.chooseWithLimit",
        statementKey="demo.test.complex.chooseWithLimit",
        sql="SELECT id, name FROM users WHERE status = 'active' LIMIT #{limit}",
        templateSql=(
            "SELECT id, name FROM users <choose>"
            "<when test=\"statusFilter == 'active'\">WHERE status = 'active'</when>"
            "<when test=\"statusFilter == 'pending'\">WHERE status = 'pending'</when>"
            "<otherwise>WHERE 1=1</otherwise>"
            "</choose> <if test=\"limit != null\">LIMIT #{limit}</if>"
        ),
        dynamicFeatures=["CHOOSE", "IF"],
    )

    assert primary_row["conflictReason"] == "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER"
    assert (
        not_target_boundary_pattern(
            "demo.test.complex.chooseBasic",
            choose_basic_sql_unit,
            "IF_GUARDED_FILTER_STATEMENT",
        )
        == "CHOOSE_GUARDED_FILTER_EXTENSION"
    )
    assert (
        not_target_boundary_pattern(
            "demo.test.complex.chooseWithLimit",
            choose_limit_sql_unit,
            "IF_GUARDED_FILTER_STATEMENT",
        )
        == "CHOOSE_GUARDED_FILTER_EXTENSION"
    )


def test_build_statement_convergence_row_labels_selected_but_unsupported_strategy_as_no_candidate() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.leftJoinWithNull",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.leftJoinWithNull",
                statementKey="demo.test.complex.leftJoinWithNull",
                selectedCandidateId="opt-1",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.leftJoinWithNull",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_leftJoinWithNull/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.leftJoinWithNull",
            statementKey="demo.test.complex.leftJoinWithNull",
            sql="SELECT o.id, o.order_no, u.name as user_name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.status = 'pending'",
            templateSql="SELECT o.id, o.order_no, u.name as user_name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.status = 'pending'",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "opt-1", "rewriteStrategy": "join_type_conversion"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_JOIN_TYPE_CHANGE"


def test_build_statement_convergence_row_clarifies_unsupported_in_subquery_rewrite() -> None:
    sql_unit, rows, proposal = _batch6_row(
        sql_key="demo.test.complex.inSubquery",
        sql="SELECT u.id FROM users u WHERE u.id IN (SELECT o.user_id FROM orders o WHERE o.status = 'active')",
        template_sql="SELECT u.id FROM users u WHERE u.id IN (SELECT o.user_id FROM orders o WHERE o.status = 'active')",
    )
    proposal.update(
        {
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY",
                "rawCandidateCount": 2,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "rawRewriteStrategies": ["subquery_to_exists", "subquery_to_join"],
            }
        }
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.inSubquery",
        rows=rows,
        sql_key="demo.test.complex.inSubquery",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_inSubquery/index.json"),
        sql_unit=sql_unit,
        proposal=proposal,
    )

    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_IN_SUBQUERY_REWRITE"


def test_build_statement_convergence_row_clarifies_exists_null_check_tail() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.existsSubquery",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.existsSubquery",
                statementKey="demo.test.complex.existsSubquery",
                selectedCandidateId="opt-2",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.existsSubquery",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_existsSubquery/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.existsSubquery",
            statementKey="demo.test.complex.existsSubquery",
            sql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)",
            templateSql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)",
        ),
        proposal={
            "candidateGenerationDiagnostics": {
                "rawRewriteStrategies": ["EXISTS_TO_JOIN", "NULL_CHECK"],
            },
            "llmCandidates": [
                {"id": "opt-1", "rewriteStrategy": "EXISTS_TO_JOIN"},
                {"id": "opt-2", "rewriteStrategy": "NULL_CHECK"},
            ],
        },
    )

    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_EXISTS_NULL_CHECK"


def test_validate_status_conflict_reason_prefers_specific_validate_feedback_reason() -> None:
    reason = validate_status_conflict_reason(
        [
            {
                "status": "NEED_MORE_PARAMS",
                "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"},
                "perfComparison": {"reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"]},
            }
        ]
    )

    assert reason == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"


def test_validate_status_conflict_reason_clarifies_row_count_semantic_error() -> None:
    reason = validate_status_conflict_reason(
        [
            {
                "status": "NEED_MORE_PARAMS",
                "feedback": {"reason_code": "VALIDATE_SEMANTIC_ERROR"},
                "semanticEquivalence": {
                    "status": "UNCERTAIN",
                    "reasons": [
                        "SEMANTIC_PREDICATE_STABLE",
                        "SEMANTIC_PROJECTION_STABLE",
                        "SEMANTIC_ROW_COUNT_ERROR",
                    ],
                },
            }
        ]
    )

    assert reason == "VALIDATE_SEMANTIC_ROW_COUNT_ERROR"


def test_semantic_conflict_reason_prefers_specific_semantic_check_reason() -> None:
    reason = semantic_conflict_reason(
        [
            {
                "semanticEquivalence": {
                    "status": "UNCERTAIN",
                    "checks": {
                        "predicate": {"status": "UNCERTAIN", "reasonCode": "SEMANTIC_PREDICATE_CHANGED"},
                        "projection": {"status": "PASS", "reasonCode": "SEMANTIC_PROJECTION_STABLE"},
                    },
                    "reasons": ["SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PROJECTION_STABLE"],
                    "hardConflicts": [],
                }
            }
        ]
    )

    assert reason == "SEMANTIC_PREDICATE_CHANGED"


def test_semantic_conflict_reason_prefers_predicate_conjunct_removed_reason() -> None:
    reason = semantic_conflict_reason(
        [
            {
                "semanticEquivalence": {
                    "status": "UNCERTAIN",
                    "checks": {
                        "predicate": {"status": "UNCERTAIN", "reasonCode": "SEMANTIC_PREDICATE_CONJUNCT_REMOVED"},
                        "projection": {"status": "PASS", "reasonCode": "SEMANTIC_PROJECTION_STABLE"},
                    },
                    "reasons": ["SEMANTIC_PREDICATE_CONJUNCT_REMOVED", "SEMANTIC_PROJECTION_STABLE"],
                    "hardConflicts": [],
                }
            }
        ]
    )

    assert reason == "SEMANTIC_PREDICATE_CONJUNCT_REMOVED"


def test_semantic_conflict_reason_preserves_and_order_equivalent_reason() -> None:
    reason = semantic_conflict_reason(
        [
            {
                "semanticEquivalence": {
                    "status": "UNCERTAIN",
                    "checks": {
                        "predicate": {"status": "UNCERTAIN", "reasonCode": "SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT"},
                        "projection": {"status": "PASS", "reasonCode": "SEMANTIC_PROJECTION_STABLE"},
                    },
                    "reasons": ["SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT", "SEMANTIC_PROJECTION_STABLE"],
                    "hardConflicts": [],
                }
            }
        ]
    )

    assert reason == "SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT"


def test_build_statement_convergence_row_accepts_and_order_equivalence_override() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.order.harness.listOrdersWithUsersPaged",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.harness.listOrdersWithUsersPaged",
                statementKey="demo.order.harness.listOrdersWithUsersPaged",
                semanticEquivalence={
                    "status": "PASS",
                    "checks": {
                        "predicate": {
                            "status": "PASS",
                            "reasonCode": "SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT",
                        },
                        "projection": {"status": "PASS", "reasonCode": "SEMANTIC_PROJECTION_STABLE"},
                        "ordering": {"status": "PASS", "reasonCode": "SEMANTIC_ORDERING_STABLE"},
                        "pagination": {"status": "PASS", "reasonCode": "SEMANTIC_PAGINATION_STABLE"},
                    },
                    "reasons": [
                        "SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT",
                        "SEMANTIC_PROJECTION_STABLE",
                        "SEMANTIC_ORDERING_STABLE",
                        "SEMANTIC_PAGINATION_STABLE",
                        "SEMANTIC_KNOWN_EQUIVALENCE_PREDICATE_AND_ORDER",
                    ],
                    "hardConflicts": [],
                },
            )
        ],
        sql_key="demo.order.harness.listOrdersWithUsersPaged",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_harness_listOrdersWithUsersPaged/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.order.harness.listOrdersWithUsersPaged",
            statementKey="demo.order.harness.listOrdersWithUsersPaged",
            sql=(
                "SELECT o.id, o.order_no, u.name AS user_name "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "WHERE o.status = #{status} AND (u.name ILIKE #{keyword} OR u.email ILIKE #{keyword}) "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            templateSql=(
                "SELECT o.id, o.order_no, u.name AS user_name "
                "FROM orders o JOIN users u ON u.id = o.user_id "
                "<where><if test=\"status != null\">o.status = #{status}</if>"
                "<if test=\"keyword != null\">AND (u.name ILIKE #{keyword} OR u.email ILIKE #{keyword})</if></where> "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            dynamicFeatures=["WHERE", "IF"],
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "predicate_reorder"}],
        },
    )

    assert row["convergenceDecision"] == "AUTO_PATCHABLE"


def test_build_statement_convergence_row_keeps_semantic_risk_tail_blocked_even_with_pass_row() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.existsSubquery",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.existsSubquery",
                statementKey="demo.test.complex.existsSubquery",
                rewriteFacts={
                    "dynamicTemplate": {
                        "capabilityProfile": {
                            "shapeFamily": "STATIC_STATEMENT",
                            "baselineFamily": "STATIC_STATEMENT_REWRITE",
                            "patchSurface": "statement",
                        }
                    }
                },
            )
        ],
        sql_key="demo.test.complex.existsSubquery.variant",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_existsSubquery/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.existsSubquery",
            statementKey="demo.test.complex.existsSubquery",
            sql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)",
            templateSql="SELECT id, name FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY"}],
        },
    )

    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "SEMANTIC_RISK_TAIL_BLOCKED"


def test_infer_shape_family_from_sql_unit_keeps_plain_static_join_in_static_statement() -> None:
    shape = infer_shape_family_from_sql_unit(
        _sql_unit(
            sql=(
                "SELECT u.id, u.name, o.order_no "
                "FROM users u JOIN orders o ON o.user_id = u.id "
                "WHERE u.status = #{status} ORDER BY u.created_at DESC"
            ),
            templateSql=(
                "SELECT u.id, u.name, o.order_no "
                "FROM users u JOIN orders o ON o.user_id = u.id "
                "WHERE u.status = #{status} ORDER BY u.created_at DESC"
            ),
        )
    )

    assert shape == "STATIC_STATEMENT"


def test_infer_shape_family_from_sql_unit_keeps_mixed_column_or_in_static_statement() -> None:
    shape = infer_shape_family_from_sql_unit(
        _sql_unit(
            sql="SELECT id, name FROM users WHERE status = 'active' OR type = 'internal'",
            templateSql="SELECT id, name FROM users WHERE status = 'active' OR type = 'internal'",
        )
    )

    assert shape == "STATIC_STATEMENT"


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


def test_build_statement_convergence_row_locks_batch6_candidate_pool_blockers() -> None:
    cases = [
        {
            "sqlKey": "demo.order.harness.listOrdersWithUsersPaged",
            "sql": (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email FROM orders AS o "
                "JOIN users AS u ON u.id = o.user_id WHERE o.status = #{status} "
                "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            "templateSql": (
                "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                "u.name AS user_name, u.email AS user_email FROM orders AS o "
                "JOIN users AS u ON u.id = o.user_id <where><if test=\"status != null and status != ''\">"
                " AND o.status = #{status}</if></where> ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
            ),
            "dynamicFeatures": ["WHERE", "IF"],
            "selectedCandidateId": "opt-003",
            "semanticStatus": "UNCERTAIN",
            "proposal": {"candidateGenerationDiagnostics": {"degradationKind": "EMPTY_CANDIDATES"}},
            "expectedReason": "SEMANTIC_GATE_NOT_PASS",
        },
        {
            "sqlKey": "demo.shipment.harness.findShipments",
            "sql": (
                "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments "
                "WHERE status = #{status} AND carrier = #{carrier} ORDER BY shipped_at DESC"
            ),
            "templateSql": (
                "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments "
                "<where><if test=\"status != null and status != ''\"> AND status = #{status}</if>"
                "<if test=\"carrier != null and carrier != ''\"> AND carrier = #{carrier}</if></where> "
                "ORDER BY shipped_at DESC"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE", "IF"],
            "proposal": {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 2,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            },
            "expectedReason": "NO_SAFE_BASELINE_RECOVERY",
        },
        {
            "sqlKey": "demo.test.complex.staticSimpleSelect",
            "sql": "SELECT id, name, email, status, created_at FROM users",
            "expectedReason": "NO_SAFE_BASELINE_RECOVERY",
            "proposal": {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "EMPTY_CANDIDATES",
                    "recoveryReason": "NO_SAFE_BASELINE_SHAPE_MATCH",
                    "rawCandidateCount": 0,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            },
        },
        {
            "sqlKey": "demo.test.complex.inSubquery",
            "sql": "SELECT u.id, u.name FROM users u WHERE u.id IN (SELECT o.user_id FROM orders o WHERE o.status = 'active')",
            "expectedReason": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            "proposal": {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 1,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            },
        },
        {
            "sqlKey": "demo.test.complex.includeSimple",
            "sql": "SELECT id, name, email, status, created_at FROM users",
            "templateSql": "SELECT <include refid=\"BaseColumns\" /> FROM users",
            "dynamicFeatures": ["INCLUDE"],
            "expectedReason": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            "proposal": {
                "candidateGenerationDiagnostics": {
                    "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                    "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                    "rawCandidateCount": 1,
                    "acceptedCandidateCount": 0,
                    "finalCandidateCount": 0,
                }
            },
        },
    ]

    for case in cases:
        sql_unit, rows, proposal = _batch6_row(
            sql_key=str(case["sqlKey"]),
            sql=str(case["sql"]),
            template_sql=str(case.get("templateSql") or case["sql"]),
            dynamic_features=list(case.get("dynamicFeatures") or []),
            selected_candidate_id=str(case.get("selectedCandidateId") or ""),
            semantic_status=str(case.get("semanticStatus") or "PASS"),
        )
        proposal.update(case.get("proposal") or {})
        row = build_statement_convergence_row(
            statement_key_value=str(case["sqlKey"]),
            rows=rows,
            sql_key=str(case["sqlKey"]),
            acceptance_path=Path("artifacts/acceptance.jsonl"),
            sql_index_path=Path(f"sql/{str(case['sqlKey']).replace('.', '_')}/index.json"),
            sql_unit=sql_unit,
            proposal=proposal,
        )
        assert row["convergenceDecision"] == "MANUAL_REVIEW"
        assert row["conflictReason"] == case["expectedReason"]
        assert row["conflictReason"] != "SHAPE_FAMILY_NOT_TARGET"


def test_build_statement_convergence_row_keeps_batch6_blocked_boundaries_on_shape_family_not_target() -> None:
    cases = [
        {
            "sqlKey": "demo.order.harness.findOrdersByNos",
            "sql": (
                "SELECT id, user_id, order_no, amount, status, created_at FROM orders WHERE #{orderNo}"
            ),
            "templateSql": (
                "SELECT <include refid=\"OrderHarnessColumns\" /> FROM orders "
                "<where><foreach collection=\"orderNos\" item=\"orderNo\" open=\"order_no IN (\" separator=\",\" close=\")\">"
                "#{orderNo}</foreach></where>"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
        },
        {
            "sqlKey": "demo.shipment.harness.findShipmentsByOrderIds",
            "sql": "SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments WHERE #{orderId}",
            "templateSql": (
                "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments "
                "<where><foreach collection=\"orderIds\" item=\"orderId\" open=\"order_id IN (\" separator=\",\" close=\")\">"
                "#{orderId}</foreach></where>"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE", "FOREACH"],
        },
        {
            "sqlKey": "demo.test.complex.multiFragmentSeparate",
            "sql": "SELECT id, name, email, status, created_at FROM users WHERE WHERE status = 'active'",
            "templateSql": (
                "SELECT <include refid=\"BaseColumns\" /> FROM users "
                "<where><include refid=\"Frag_Where_Active\" /></where>"
            ),
            "dynamicFeatures": ["INCLUDE", "WHERE"],
            "semanticStatus": "UNCERTAIN",
        },
        {
            "sqlKey": "demo.test.complex.selectWithFragmentChoose",
            "sql": "SELECT id, name, email FROM users (ORDER BY name ASC OR ORDER BY name DESC OR ORDER BY id ASC)",
            "templateSql": (
                "SELECT id, name, email FROM users <choose>"
                "<when test=\"sort == 'asc'\"><include refid=\"Frag_Order_ASC\" /></when>"
                "<when test=\"sort == 'desc'\"><include refid=\"Frag_Order_DESC\" /></when>"
                "<otherwise><include refid=\"Frag_Order_Default\" /></otherwise>"
                "</choose>"
            ),
            "dynamicFeatures": ["CHOOSE", "INCLUDE"],
            "expectedReason": "NO_PATCHABLE_CANDIDATE_UNSUPPORTED_STRATEGY",
        },
    ]

    for case in cases:
        sql_unit, rows, proposal = _batch6_row(
            sql_key=str(case["sqlKey"]),
            sql=str(case["sql"]),
            template_sql=str(case["templateSql"]),
            dynamic_features=list(case.get("dynamicFeatures") or []),
        )
        row = build_statement_convergence_row(
            statement_key_value=str(case["sqlKey"]),
            rows=rows,
            sql_key=str(case["sqlKey"]),
            acceptance_path=Path("artifacts/acceptance.jsonl"),
            sql_index_path=Path(f"sql/{str(case['sqlKey']).replace('.', '_')}/index.json"),
            sql_unit=sql_unit,
            proposal=proposal,
        )
        assert row["convergenceDecision"] == "MANUAL_REVIEW"
        assert row["conflictReason"] == case.get("expectedReason", "SHAPE_FAMILY_NOT_TARGET")


def test_build_statement_convergence_row_keeps_existing_dynamic_safe_baseline_out_of_no_safe_recovery_bucket() -> None:
    sql_unit, rows, proposal = _batch6_row(
        sql_key="demo.user.aliasCleanup",
        sql=(
            "SELECT id AS id, name AS name FROM users "
            "WHERE status = #{status} ORDER BY created_at DESC"
        ),
        template_sql=(
            "SELECT id AS id, name AS name FROM users "
            "<where><if test=\"status != null\">status = #{status}</if></where> "
            "ORDER BY created_at DESC"
        ),
        dynamic_features=["WHERE", "IF"],
    )
    proposal.update(
        {
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 1,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            }
        }
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.aliasCleanup",
        rows=rows,
        sql_key="demo.user.aliasCleanup",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_aliasCleanup/index.json"),
        sql_unit=sql_unit,
        proposal=proposal,
    )

    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY"


def test_build_statement_convergence_row_keeps_plain_foreach_boundary_out_of_no_safe_recovery_lane() -> None:
    sql_unit, rows, proposal = _batch6_row(
        sql_key="demo.shipment.harness.findShipmentsByOrderIds",
        sql="SELECT id, order_id, carrier, tracking_no, status, shipped_at FROM shipments WHERE #{orderId}",
        template_sql=(
            "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments "
            "<where><foreach collection=\"orderIds\" item=\"orderId\" open=\"order_id IN (\" separator=\",\" close=\")\">"
            "#{orderId}</foreach></where>"
        ),
        dynamic_features=["INCLUDE", "WHERE", "FOREACH"],
    )
    proposal.update(
        {
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 1,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            }
        }
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.shipment.harness.findShipmentsByOrderIds",
        rows=rows,
        sql_key="demo.shipment.harness.findShipmentsByOrderIds",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_shipment_harness_findShipmentsByOrderIds/index.json"),
        sql_unit=sql_unit,
        proposal=proposal,
    )

    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "SHAPE_FAMILY_NOT_TARGET"


def test_not_target_boundary_no_longer_marks_supported_choose_guarded_filter_as_promote_next() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "SELECT id, name FROM users <where><choose>"
            "<when test=\"keyword != null\">name ILIKE #{keywordPattern}</when>"
            "<otherwise>status != 'DELETED'</otherwise></choose></where>"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    assert (
        not_target_boundary_pattern(
            "demo.user.advanced.findUsersByKeyword",
            sql_unit,
            "IF_GUARDED_FILTER_STATEMENT",
        )
        is None
    )
    assert (
        not_target_boundary_bucket(
            "demo.user.advanced.findUsersByKeyword",
            sql_unit,
            "IF_GUARDED_FILTER_STATEMENT",
        )
        is None
    )


def test_not_target_boundary_keeps_plain_foreach_include_predicates_blocked() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.order.harness.findOrdersByNos",
        statementKey="demo.order.harness.findOrdersByNos",
        sql="SELECT id FROM orders WHERE #{orderNo}",
        templateSql=(
            "SELECT <include refid=\"OrderHarnessColumns\" /> FROM orders "
            "<where><foreach collection=\"orderNos\" item=\"orderNo\">#{orderNo}</foreach></where>"
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "FOREACH"],
    )

    assert (
        not_target_boundary_pattern(
            "demo.order.harness.findOrdersByNos",
            sql_unit,
            "UNKNOWN",
        )
        == "PLAIN_FOREACH_INCLUDE_PREDICATE"
    )
    assert (
        not_target_boundary_bucket(
            "demo.order.harness.findOrdersByNos",
            sql_unit,
            "UNKNOWN",
        )
        == "keep_blocked"
    )


def test_not_target_boundary_keeps_ambiguous_fragment_chain_blocked() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.multiFragmentSeparate",
        statementKey="demo.test.complex.multiFragmentSeparate",
        sql="SELECT id, name, email, status, created_at FROM users WHERE WHERE status = 'active'",
        templateSql=(
            "SELECT <include refid=\"BaseColumns\"/> FROM users "
            "<where><include refid=\"Frag_Where_Active\"/></where>"
        ),
        dynamicFeatures=["INCLUDE", "WHERE"],
    )

    assert (
        not_target_boundary_pattern(
            "demo.test.complex.multiFragmentSeparate",
            sql_unit,
            "UNKNOWN",
        )
        == "AMBIGUOUS_FRAGMENT_CHAIN"
    )
    assert (
        not_target_boundary_bucket(
            "demo.test.complex.multiFragmentSeparate",
            sql_unit,
            "UNKNOWN",
        )
        == "keep_blocked"
    )


def test_generalization_batch5_candidate_pool_is_choose_extension_only() -> None:
    assert GENERALIZATION_BATCH5_SQL_KEYS == (
        "demo.user.advanced.findUsersByKeyword",
        "demo.test.complex.chooseBasic",
        "demo.test.complex.chooseMultipleWhen",
        "demo.test.complex.chooseWithLimit",
        "demo.test.complex.selectWithFragmentChoose",
    )


def test_generalization_batch6_candidate_pool_targets_shared_candidate_selection_gap() -> None:
    assert GENERALIZATION_BATCH6_SQL_KEYS == (
        "demo.order.harness.listOrdersWithUsersPaged",
        "demo.shipment.harness.findShipments",
        "demo.test.complex.staticSimpleSelect",
        "demo.test.complex.inSubquery",
        "demo.test.complex.includeSimple",
    )


def test_batch6_candidate_pool_stays_inside_supported_or_near_supported_shapes() -> None:
    candidate_cases = [
        (
            "demo.order.harness.listOrdersWithUsersPaged",
            _sql_unit(
                sqlKey="demo.order.harness.listOrdersWithUsersPaged",
                statementKey="demo.order.harness.listOrdersWithUsersPaged",
                sql=(
                    "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                    "u.name AS user_name, u.email AS user_email "
                    "FROM orders AS o JOIN users AS u ON u.id = o.user_id "
                    "WHERE o.status = #{status} ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
                ),
                templateSql=(
                    "SELECT o.id, o.order_no, o.user_id, o.amount, o.status, o.created_at, "
                    "u.name AS user_name, u.email AS user_email "
                    "FROM orders AS o JOIN users AS u ON u.id = o.user_id "
                    "<where><if test=\"status != null\">o.status = #{status}</if></where> "
                    "ORDER BY o.created_at DESC LIMIT #{limit} OFFSET #{offset}"
                ),
                dynamicFeatures=["WHERE", "IF"],
            ),
        ),
        (
            "demo.shipment.harness.findShipments",
            _sql_unit(
                sqlKey="demo.shipment.harness.findShipments",
                statementKey="demo.shipment.harness.findShipments",
                sql=(
                    "SELECT id, order_id, carrier, tracking_no, status, shipped_at "
                    "FROM shipments AS s WHERE status = #{status} AND carrier = #{carrier} "
                    "ORDER BY shipped_at DESC"
                ),
                templateSql=(
                    "SELECT <include refid=\"ShipmentHarnessColumns\"/> FROM shipments AS s "
                    "<where><if test=\"status != null\">status = #{status}</if>"
                    "<if test=\"carrier != null\">AND carrier = #{carrier}</if></where> "
                    "ORDER BY shipped_at DESC"
                ),
                dynamicFeatures=["INCLUDE", "WHERE", "IF"],
            ),
        ),
        (
            "demo.test.complex.staticSimpleSelect",
            _sql_unit(
                sqlKey="demo.test.complex.staticSimpleSelect",
                statementKey="demo.test.complex.staticSimpleSelect",
                sql="SELECT * FROM users",
                templateSql="SELECT * FROM users",
                dynamicFeatures=[],
            ),
        ),
        (
            "demo.test.complex.inSubquery",
            _sql_unit(
                sqlKey="demo.test.complex.inSubquery",
                statementKey="demo.test.complex.inSubquery",
                sql="SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
                templateSql="SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)",
                dynamicFeatures=[],
            ),
        ),
        (
            "demo.test.complex.includeSimple",
            _sql_unit(
                sqlKey="demo.test.complex.includeSimple",
                statementKey="demo.test.complex.includeSimple",
                sql="SELECT * FROM users",
                templateSql="SELECT <include refid=\"BaseColumns\"/> FROM users",
                dynamicFeatures=["INCLUDE"],
            ),
        ),
    ]

    for statement_key_value, sql_unit in candidate_cases:
        shape_family = infer_shape_family_from_sql_unit(sql_unit)
        assert not_target_boundary_pattern(statement_key_value, sql_unit, shape_family) is None
        assert not_target_boundary_bucket(statement_key_value, sql_unit, shape_family) is None


def test_not_target_boundary_keeps_plain_foreach_include_shipments_blocked() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.shipment.harness.findShipmentsByOrderIds",
        statementKey="demo.shipment.harness.findShipmentsByOrderIds",
        sql="SELECT id FROM shipments WHERE #{orderId}",
        templateSql=(
            "SELECT <include refid=\"ShipmentHarnessColumns\" /> FROM shipments AS s "
            "<where><foreach collection=\"orderIds\" item=\"orderId\">#{orderId}</foreach></where>"
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "FOREACH"],
    )

    assert (
        not_target_boundary_pattern(
            "demo.shipment.harness.findShipmentsByOrderIds",
            sql_unit,
            "UNKNOWN",
        )
        == "PLAIN_FOREACH_INCLUDE_PREDICATE"
    )
    assert (
        not_target_boundary_bucket(
            "demo.shipment.harness.findShipmentsByOrderIds",
            sql_unit,
            "UNKNOWN",
        )
        == "keep_blocked"
    )


def test_batch5_choose_statements_support_only_filter_shaped_choose_cases() -> None:
    supported_cases = [
        (
            "demo.user.advanced.findUsersByKeyword",
            _sql_unit(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                sql="SELECT id, name, email, status, created_at, updated_at FROM users AS u WHERE status != 'DELETED' ORDER BY created_at DESC",
                templateSql=(
                    "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
                    "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
                    "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
                    "<when test=\"status != null and status != ''\">status = #{status}</when>"
                    "<otherwise>status != 'DELETED'</otherwise>"
                    "</choose></where> ORDER BY created_at DESC"
                ),
                dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
            ),
        ),
    ]
    unsupported_cases = [
        (
            "demo.test.complex.chooseBasic",
            _sql_unit(
                sqlKey="demo.test.complex.chooseBasic",
                statementKey="demo.test.complex.chooseBasic",
                sql="SELECT id, name FROM users WHERE 1=1",
                templateSql=(
                    "SELECT id, name FROM users <choose>"
                    "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
                    "<when test=\"type == 'inactive'\">WHERE status = 'inactive'</when>"
                    "<otherwise>WHERE 1=1</otherwise>"
                    "</choose>"
                ),
                dynamicFeatures=["CHOOSE"],
            ),
        ),
        (
            "demo.test.complex.chooseMultipleWhen",
            _sql_unit(
                sqlKey="demo.test.complex.chooseMultipleWhen",
                statementKey="demo.test.complex.chooseMultipleWhen",
                sql="SELECT id, name, status FROM users WHERE status = 'active'",
                templateSql=(
                    "SELECT id, name, status FROM users <choose>"
                    "<when test=\"role == 'admin'\">WHERE 1=1</when>"
                    "<when test=\"role == 'user'\">WHERE status = 'active'</when>"
                    "<otherwise>WHERE status != 'deleted'</otherwise>"
                    "</choose>"
                ),
                dynamicFeatures=["CHOOSE"],
            ),
        ),
        (
            "demo.test.complex.chooseWithLimit",
            _sql_unit(
                sqlKey="demo.test.complex.chooseWithLimit",
                statementKey="demo.test.complex.chooseWithLimit",
                sql="SELECT id, name FROM users WHERE status = 'active' LIMIT #{limit}",
                templateSql=(
                    "SELECT id, name FROM users <choose>"
                    "<when test=\"statusFilter == 'active'\">WHERE status = 'active'</when>"
                    "<when test=\"statusFilter == 'pending'\">WHERE status = 'pending'</when>"
                    "<otherwise>WHERE 1=1</otherwise>"
                    "</choose> <if test=\"limit != null\">LIMIT #{limit}</if>"
                ),
                dynamicFeatures=["CHOOSE", "IF"],
            ),
        ),
        (
            "demo.test.complex.selectWithFragmentChoose",
            _sql_unit(
                sqlKey="demo.test.complex.selectWithFragmentChoose",
                statementKey="demo.test.complex.selectWithFragmentChoose",
                sql="SELECT id, name, email FROM users ORDER BY name ASC",
                templateSql=(
                    "SELECT id, name, email FROM users <choose>"
                    "<when test=\"sort == 'asc'\"><include refid=\"Frag_Order_ASC\"/></when>"
                    "<when test=\"sort == 'desc'\"><include refid=\"Frag_Order_DESC\"/></when>"
                    "<otherwise><include refid=\"Frag_Order_Default\"/></otherwise>"
                    "</choose>"
                ),
                dynamicFeatures=["CHOOSE", "INCLUDE"],
            ),
        ),
    ]

    for statement_key_value, sql_unit in supported_cases:
        assert infer_shape_family_from_sql_unit(sql_unit) == "IF_GUARDED_FILTER_STATEMENT"
        assert not_target_boundary_pattern(statement_key_value, sql_unit, "IF_GUARDED_FILTER_STATEMENT") is None
        assert not_target_boundary_bucket(statement_key_value, sql_unit, "IF_GUARDED_FILTER_STATEMENT") is None

    for unsupported_statement_key, unsupported_sql_unit in unsupported_cases:
        assert infer_shape_family_from_sql_unit(unsupported_sql_unit) == "IF_GUARDED_FILTER_STATEMENT"
        assert (
            not_target_boundary_pattern(
                unsupported_statement_key,
                unsupported_sql_unit,
                "IF_GUARDED_FILTER_STATEMENT",
            )
            == "CHOOSE_GUARDED_FILTER_EXTENSION"
        )
        assert (
            not_target_boundary_bucket(
                unsupported_statement_key,
                unsupported_sql_unit,
                "IF_GUARDED_FILTER_STATEMENT",
            )
            == "promote_next"
        )


def test_build_statement_convergence_row_reports_low_value_only_for_supported_choose_filter_shape() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
            "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
            "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
            "<when test=\"status != null and status != ''\">status = #{status}</when>"
            "<otherwise>status != 'DELETED'</otherwise>"
            "</choose></where> ORDER BY created_at DESC"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 3,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            },
        },
    )

    assert row["shapeFamily"] == "FOREACH_COLLECTION_PREDICATE"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY"


def test_build_statement_convergence_row_keeps_low_value_blocker_for_mixed_choose_keyword_candidate_pool() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
            "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
            "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
            "<when test=\"status != null and status != ''\">status = #{status}</when>"
            "<otherwise>status != 'DELETED'</otherwise>"
            "</choose></where> ORDER BY created_at DESC"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 3,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "rawRewriteStrategies": [
                    "union_or_elimination",
                    "redundant_condition_removal",
                    "index_driven_union",
                ],
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "SEMANTIC_RISK_REWRITE"},
                    {"candidateId": "opt-002", "category": "NO_SAFE_BASELINE_MATCH"},
                    {"candidateId": "opt-003", "category": "UNSUPPORTED_STRATEGY"},
                ],
            },
        },
    )

    assert row["shapeFamily"] == "FOREACH_COLLECTION_PREDICATE"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_RECOVERY"


def test_build_statement_convergence_row_keeps_choose_filter_low_value_only_without_no_safe_baseline_signal() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
            "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
            "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
            "<when test=\"status != null and status != ''\">status = #{status}</when>"
            "<otherwise>status != 'DELETED'</otherwise>"
            "</choose></where> ORDER BY created_at DESC"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 2,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "SEMANTIC_RISK_REWRITE"},
                    {"candidateId": "opt-002", "category": "UNSUPPORTED_STRATEGY"},
                ],
            },
        },
    )

    assert row["shapeFamily"] == "IF_GUARDED_FILTER_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY"


def test_build_statement_convergence_row_clarifies_foreach_include_safe_baseline_gap() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.order.harness.findOrdersByUserIdsAndStatus",
        statementKey="demo.order.harness.findOrdersByUserIdsAndStatus",
        sql=(
            "SELECT id, user_id, order_no, amount, status, created_at "
            "FROM orders WHERE user_id IN (#{userId}) AND status = #{status}"
        ),
        templateSql=(
            "SELECT <include refid=\"OrderColumns\" /> FROM orders <where>"
            "<foreach collection=\"userIds\" item=\"userId\" open=\"user_id IN (\" separator=\",\" close=\")\">"
            "#{userId}</foreach>"
            "<if test=\"status != null and status != ''\">AND status = #{status}</if>"
            "</where>"
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "FOREACH", "IF"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.order.harness.findOrdersByUserIdsAndStatus",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.harness.findOrdersByUserIdsAndStatus",
                statementKey="demo.order.harness.findOrdersByUserIdsAndStatus",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.order.harness.findOrdersByUserIdsAndStatus",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_harness_findOrdersByUserIdsAndStatus/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 2,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "NO_SAFE_BASELINE_MATCH"},
                    {"candidateId": "opt-002", "category": "SEMANTIC_RISK_REWRITE"},
                ],
            },
        },
    )

    assert row["shapeFamily"] == "FOREACH_COLLECTION_PREDICATE"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE"


def test_build_statement_convergence_row_clarifies_choose_guarded_safe_baseline_gap() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
            "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
            "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
            "<when test=\"status != null and status != ''\">status = #{status}</when>"
            "<otherwise>status != 'DELETED'</otherwise>"
            "</choose></where> ORDER BY created_at DESC"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 3,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "NO_SAFE_BASELINE_MATCH"},
                    {"candidateId": "opt-002", "category": "NO_SAFE_BASELINE_MATCH"},
                    {"candidateId": "opt-003", "category": "NO_SAFE_BASELINE_MATCH"},
                ],
            },
        },
    )

    assert row["shapeFamily"] == "IF_GUARDED_FILTER_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_CHOOSE_GUARDED_FILTER"


def test_build_statement_convergence_row_clarifies_multi_fragment_include_safe_baseline_gap() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.multiFragmentLevel1",
        statementKey="demo.test.complex.multiFragmentLevel1",
        sql="SELECT id, name, email, status FROM users",
        templateSql='SELECT <include refid="Frag_Cols_Basic" />, <include refid="Frag_Cols_Contact" /> FROM users',
        dynamicFeatures=["INCLUDE"],
        includeBindings=[
            {"ref": "demo.test.complex.Frag_Cols_Basic", "properties": [], "bindingHash": "basic"},
            {"ref": "demo.test.complex.Frag_Cols_Contact", "properties": [], "bindingHash": "contact"},
        ],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.multiFragmentLevel1",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.multiFragmentLevel1",
                statementKey="demo.test.complex.multiFragmentLevel1",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.multiFragmentLevel1",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_multiFragmentLevel1/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "EMPTY_CANDIDATES",
                "recoveryReason": "NO_SAFE_BASELINE_SHAPE_MATCH",
                "rawCandidateCount": 0,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            },
        },
    )

    assert row["shapeFamily"] == MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE"


def test_build_statement_convergence_row_keeps_multi_fragment_include_review_only_even_with_candidate_and_family() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.multiFragmentLevel1",
        statementKey="demo.test.complex.multiFragmentLevel1",
        sql="SELECT id, name, email, mobile, phone FROM users WHERE status = 'ACTIVE'",
        templateSql=(
            'SELECT <include refid="demo.test.complex.Frag_Cols_Basic" />,'
            ' <include refid="demo.test.complex.Frag_Cols_Contact" /> FROM users'
            ' <where><if test="activeOnly">status = \'ACTIVE\'</if></where>'
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "IF"],
        includeBindings=[
            {"ref": "demo.test.complex.Frag_Cols_Basic", "properties": [], "bindingHash": "basic"},
            {"ref": "demo.test.complex.Frag_Cols_Contact", "properties": [], "bindingHash": "contact"},
        ],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.multiFragmentLevel1",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.multiFragmentLevel1",
                statementKey="demo.test.complex.multiFragmentLevel1",
                selectedCandidateId="opt-1",
                rewriteFacts={
                    "dynamicTemplate": {
                        "capabilityProfile": {
                            "shapeFamily": MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY,
                            "capabilityTier": "REVIEW_REQUIRED",
                            "baselineFamily": "STATIC_INCLUDE_WRAPPER_COLLAPSE",
                            "patchSurface": "STATEMENT_BODY",
                            "blockerFamily": "MULTI_FRAGMENT_INCLUDE_REVIEW_ONLY",
                        }
                    }
                },
                templateRewriteOps=[{"op": "replace_statement_body", "targetRef": "statement"}],
            )
        ],
        sql_key="demo.test.complex.multiFragmentLevel1",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_multiFragmentLevel1/index.json"),
        sql_unit=sql_unit,
        proposal={"llmCandidates": [{"id": "opt-1", "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY"}]},
    )

    assert row["shapeFamily"] == MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["consensus"] is None
    assert row["conflictReason"] == "NO_SAFE_BASELINE_MULTI_FRAGMENT_INCLUDE"


def test_build_statement_convergence_row_keeps_collection_predicate_review_only_even_with_candidate_and_family() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.order.harness.findOrdersByUserIdsAndStatus",
        statementKey="demo.order.harness.findOrdersByUserIdsAndStatus",
        sql="SELECT id, order_no, user_id, status FROM orders WHERE user_id IN (1, 2, 3) AND status = 'PAID'",
        templateSql=(
            'SELECT <include refid="OrderHarnessColumns" /> FROM orders'
            ' <where><include refid="OrderHarnessStatusFilter" />'
            ' <if test="userIds != null and userIds.size() > 0">AND user_id IN'
            ' <foreach item="id" collection="userIds" open="(" separator="," close=")">#{id}</foreach>'
            " </if></where>"
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "IF", "FOREACH"],
        includeBindings=[{"ref": "OrderHarnessStatusFilter", "properties": [], "bindingHash": "status"}],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.order.harness.findOrdersByUserIdsAndStatus",
        rows=[
            _acceptance_row(
                sqlKey="demo.order.harness.findOrdersByUserIdsAndStatus",
                statementKey="demo.order.harness.findOrdersByUserIdsAndStatus",
                selectedCandidateId="opt-2",
                rewriteFacts={
                    "dynamicTemplate": {
                        "capabilityProfile": {
                            "shapeFamily": "FOREACH_COLLECTION_PREDICATE",
                            "capabilityTier": "REVIEW_REQUIRED",
                            "baselineFamily": "STATIC_STATEMENT_REWRITE",
                            "patchSurface": "WHERE_CLAUSE",
                            "blockerFamily": "FOREACH_COLLECTION_GUARDED_PREDICATE",
                        }
                    }
                },
                templateRewriteOps=[{"op": "replace_where_clause", "targetRef": "statement"}],
            )
        ],
        sql_key="demo.order.harness.findOrdersByUserIdsAndStatus",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_order_harness_findOrdersByUserIdsAndStatus/index.json"),
        sql_unit=sql_unit,
        proposal={"llmCandidates": [{"id": "opt-2", "rewriteStrategy": "SIMPLIFY_BOOLEAN_TAUTOLOGY"}]},
    )

    assert row["shapeFamily"] == "FOREACH_COLLECTION_PREDICATE"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["consensus"] is None
    assert row["conflictReason"] == "NO_SAFE_BASELINE_COLLECTION_GUARDED_PREDICATE"


def test_build_statement_convergence_row_clarifies_speculative_limit_only_safe_baseline_gap() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.shipment.harness.findShipments",
        statementKey="demo.shipment.harness.findShipments",
        sql="SELECT id, order_id, carrier, status, shipped_at FROM shipments WHERE status = #{status} ORDER BY shipped_at DESC",
        templateSql=(
            'SELECT <include refid="ShipmentHarnessColumns" /> FROM shipments <where>'
            '<if test="status != null and status != \'\'">AND status = #{status}</if>'
            '<if test="carrier != null and carrier != \'\'">AND carrier = #{carrier}</if>'
            '</where> ORDER BY shipped_at DESC'
        ),
        dynamicFeatures=["INCLUDE", "WHERE", "IF"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.shipment.harness.findShipments",
        rows=[
            _acceptance_row(
                sqlKey="demo.shipment.harness.findShipments",
                statementKey="demo.shipment.harness.findShipments",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.shipment.harness.findShipments",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_shipment_harness_findShipments/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 1,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
                "rawRewriteStrategies": ["add_limit"],
                "lowValueAssessments": [
                    {"candidateId": "opt-001", "category": "DYNAMIC_FILTER_SPECULATIVE_REWRITE"},
                ],
            },
        },
    )

    assert row["shapeFamily"] == "IF_GUARDED_FILTER_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_SPECULATIVE_LIMIT_ONLY"


def test_build_statement_convergence_row_clarifies_group_by_safe_baseline_gap() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.staticGroupBy",
        statementKey="demo.test.complex.staticGroupBy",
        sql="SELECT status, COUNT(*) as cnt FROM users GROUP BY status",
        dynamicFeatures=[],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.staticGroupBy",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.staticGroupBy",
                statementKey="demo.test.complex.staticGroupBy",
                selectedCandidateId=None,
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.staticGroupBy",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_staticGroupBy/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "EMPTY_CANDIDATES",
                "recoveryReason": "NO_SAFE_BASELINE_GROUP_BY",
                "rawCandidateCount": 0,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            },
        },
    )

    assert row["shapeFamily"] == "STATIC_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "NO_SAFE_BASELINE_GROUP_BY"


def test_supported_choose_filter_drops_unsupported_patch_family_hint_before_reporting_validate_error() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.user.advanced.findUsersByKeyword",
        statementKey="demo.user.advanced.findUsersByKeyword",
        sql="SELECT id, name, email, status, created_at, updated_at FROM users WHERE status != 'DELETED' ORDER BY created_at DESC",
        templateSql=(
            "<bind name=\"keywordPattern\" value=\"'%' + keyword + '%'\" /> "
            "SELECT <include refid=\"AdvancedUserColumns\" /> FROM users <where><choose>"
            "<when test=\"keyword != null and keyword != ''\">name ILIKE #{keywordPattern}</when>"
            "<when test=\"status != null and status != ''\">status = #{status}</when>"
            "<otherwise>status != 'DELETED'</otherwise>"
            "</choose></where> ORDER BY created_at DESC"
        ),
        dynamicFeatures=["BIND", "INCLUDE", "WHERE", "CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.user.advanced.findUsersByKeyword",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.advanced.findUsersByKeyword",
                statementKey="demo.user.advanced.findUsersByKeyword",
                status="NEED_MORE_PARAMS",
                selectedCandidateId="tautology-removal",
                semanticEquivalence={"status": "UNCERTAIN"},
                feedback={"reason_code": "VALIDATE_SEMANTIC_ERROR"},
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.advanced.findUsersByKeyword",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_advanced_findUsersByKeyword/index.json"),
        sql_unit=sql_unit,
        proposal={
            "llmCandidates": [
                {
                    "id": "tautology-removal",
                    "rewriteStrategy": "remove_tautology",
                    "rewrittenSql": "SELECT id, name FROM users",
                }
            ],
            "candidateGenerationDiagnostics": {
                "degradationKind": None,
                "recoveryReason": "NONE",
                "rawCandidateCount": 3,
                "acceptedCandidateCount": 2,
                "finalCandidateCount": 2,
            },
        },
    )

    assert row["shapeFamily"] == "IF_GUARDED_FILTER_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "VALIDATE_SEMANTIC_ERROR"


def test_build_statement_convergence_row_prefers_validate_error_for_unsupported_bare_choose() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.chooseBasic",
        statementKey="demo.test.complex.chooseBasic",
        sql="SELECT id, name FROM users WHERE 1=1",
        templateSql=(
            "SELECT id, name FROM users <choose>"
            "<when test=\"type == 'active'\">WHERE status = 'active'</when>"
            "<when test=\"type == 'inactive'\">WHERE status = 'inactive'</when>"
            "<otherwise>WHERE 1=1</otherwise>"
            "</choose>"
        ),
        dynamicFeatures=["CHOOSE"],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.chooseBasic",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.chooseBasic",
                statementKey="demo.test.complex.chooseBasic",
                status="NEED_MORE_PARAMS",
                selectedCandidateId=None,
                feedback={"reason_code": "VALIDATE_SEMANTIC_ERROR"},
                semanticEquivalence={"status": "UNCERTAIN"},
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.chooseBasic",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_chooseBasic/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": "ONLY_LOW_VALUE_CANDIDATES",
                "recoveryReason": "LOW_VALUE_PRUNED_TO_EMPTY",
                "rawCandidateCount": 2,
                "acceptedCandidateCount": 0,
                "finalCandidateCount": 0,
            },
        },
    )

    assert row["shapeFamily"] == "IF_GUARDED_FILTER_STATEMENT"
    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "VALIDATE_SEMANTIC_ERROR"


def test_build_statement_convergence_row_clarifies_nested_include_row_count_error() -> None:
    sql_unit = _sql_unit(
        sqlKey="demo.test.complex.includeNested",
        statementKey="demo.test.complex.includeNested",
        sql="SELECT id FROM users",
        templateSql='SELECT <include refid="demo.test.complex.NestedColumns" /> FROM users',
        dynamicFeatures=["INCLUDE"],
        includeBindings=[
            {"ref": "demo.test.complex.NestedColumns", "properties": [], "bindingHash": "nested"},
        ],
    )

    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.includeNested",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.includeNested",
                statementKey="demo.test.complex.includeNested",
                status="NEED_MORE_PARAMS",
                selectedCandidateId="demo.test.complex.includeNested:llm:recovered_safe_baseline_static_include_wrapper_collapse",
                feedback={"reason_code": "VALIDATE_SEMANTIC_ERROR"},
                semanticEquivalence={
                    "status": "UNCERTAIN",
                    "reasons": [
                        "SEMANTIC_PREDICATE_STABLE",
                        "SEMANTIC_PROJECTION_STABLE",
                        "SEMANTIC_ORDERING_STABLE",
                        "SEMANTIC_PAGINATION_STABLE",
                        "SEMANTIC_ROW_COUNT_ERROR",
                    ],
                },
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "STATIC_INCLUDE_ONLY"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.includeNested",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_includeNested/index.json"),
        sql_unit=sql_unit,
        proposal={
            "candidateGenerationDiagnostics": {
                "degradationKind": None,
                "recoveryReason": "STATIC_INCLUDE_WRAPPER_COLLAPSE",
                "rawCandidateCount": 1,
                "acceptedCandidateCount": 1,
                "finalCandidateCount": 1,
            },
        },
    )

    assert row["convergenceDecision"] == "MANUAL_REVIEW"
    assert row["conflictReason"] == "VALIDATE_SEMANTIC_ROW_COUNT_ERROR"


def test_build_statement_convergence_row_accepts_subquery_elimination_for_static_include_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.user.countUser",
        rows=[
            _acceptance_row(
                sqlKey="demo.user.countUser",
                statementKey="demo.user.countUser",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.user.countUser",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_user_countUser/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.user.countUser",
            statementKey="demo.user.countUser",
            sql="SELECT COUNT(1) FROM (SELECT id, name, email FROM users) u",
            templateSql='SELECT COUNT(1) FROM (SELECT <include refid="BaseColumns"/> FROM users) u',
            dynamicFeatures=["INCLUDE"],
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "subquery-elimination"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_INCLUDE_ONLY"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_INCLUDE_PATCH_FAMILY


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


def test_build_statement_convergence_row_uses_static_wrapper_family_for_subquery_inline_strategy() -> None:
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
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SUBQUERY_INLINE"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_SUBQUERY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_accepts_subquery_flattening_for_static_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.fromClauseSubquery",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.fromClauseSubquery",
                statementKey="demo.test.complex.fromClauseSubquery",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.fromClauseSubquery",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_fromClauseSubquery/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.fromClauseSubquery",
            statementKey="demo.test.complex.fromClauseSubquery",
            sql="SELECT * FROM (SELECT id, name, status FROM users WHERE status = 'active') active_users",
            templateSql="SELECT * FROM (SELECT id, name, status FROM users WHERE status = 'active') active_users",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SUBQUERY_FLATTENING"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_SUBQUERY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_accepts_flatten_subquery_wording_for_static_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.fromClauseSubquery",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.fromClauseSubquery",
                statementKey="demo.test.complex.fromClauseSubquery",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.fromClauseSubquery",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_fromClauseSubquery/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.fromClauseSubquery",
            statementKey="demo.test.complex.fromClauseSubquery",
            sql="SELECT * FROM (SELECT id, name, status FROM users WHERE status = 'active') active_users",
            templateSql="SELECT * FROM (SELECT id, name, status FROM users WHERE status = 'active') active_users",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "flatten_subquery"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_SUBQUERY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_accepts_subquery_unnest_for_static_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.wrapperCount",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.wrapperCount",
                statementKey="demo.test.complex.wrapperCount",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.wrapperCount",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_wrapperCount/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.wrapperCount",
            statementKey="demo.test.complex.wrapperCount",
            sql="SELECT COUNT(*) FROM (SELECT id FROM users WHERE status = 'active') active_users",
            templateSql="SELECT COUNT(*) FROM (SELECT id FROM users WHERE status = 'active') active_users",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "subquery_unnest"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_SUBQUERY_WRAPPER"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY


def test_build_statement_convergence_row_accepts_structure_preserving_for_static_wrapper() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.test.complex.wrapperCount",
        rows=[
            _acceptance_row(
                sqlKey="demo.test.complex.wrapperCount",
                statementKey="demo.test.complex.wrapperCount",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.test.complex.wrapperCount",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_test_complex_wrapperCount/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.test.complex.wrapperCount",
            statementKey="demo.test.complex.wrapperCount",
            sql="SELECT COUNT(*) FROM (SELECT id FROM users WHERE status = 'active') active_users",
            templateSql="SELECT COUNT(*) FROM (SELECT id FROM users WHERE status = 'active') active_users",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "structure_preserving"}],
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


def test_build_statement_convergence_row_uses_registry_strategy_family_for_safe_join_left_to_inner() -> None:
    row = build_statement_convergence_row(
        statement_key_value="demo.orders.join",
        rows=[
            _acceptance_row(
                sqlKey="demo.orders.join",
                statementKey="demo.orders.join",
                rewriteFacts={"dynamicTemplate": {"capabilityProfile": {"shapeFamily": "UNKNOWN"}}},
                templateRewriteOps=[],
            )
        ],
        sql_key="demo.orders.join",
        acceptance_path=Path("artifacts/acceptance.jsonl"),
        sql_index_path=Path("sql/demo_orders_join/index.json"),
        sql_unit=_sql_unit(
            sqlKey="demo.orders.join",
            statementKey="demo.orders.join",
            sql="SELECT * FROM orders o LEFT JOIN users u ON u.id = o.user_id",
            templateSql="SELECT * FROM orders o LEFT JOIN users u ON u.id = o.user_id",
        ),
        proposal={
            "candidateGenerationDiagnostics": {},
            "llmCandidates": [{"id": "c1", "rewriteStrategy": "SAFE_JOIN_LEFT_TO_INNER"}],
        },
    )

    assert row["shapeFamily"] == "STATIC_STATEMENT"
    assert row["convergenceDecision"] == "AUTO_PATCHABLE"
    assert row["consensus"]["patchFamily"] == "STATIC_JOIN_LEFT_TO_INNER"


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
    assert MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY in SUPPORTED_STATIC_SHAPE_FAMILIES
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
            dynamicFeatures=["INCLUDE"],
            templateSql='SELECT <include refid="Frag_Cols_Basic" />, <include refid="Frag_Cols_Contact" /> FROM users',
            includeBindings=[
                {"ref": "demo.test.complex.Frag_Cols_Basic", "properties": [], "bindingHash": "basic"},
                {"ref": "demo.test.complex.Frag_Cols_Contact", "properties": [], "bindingHash": "contact"},
            ],
        )
    ) == MULTI_FRAGMENT_INCLUDE_SHAPE_FAMILY
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
