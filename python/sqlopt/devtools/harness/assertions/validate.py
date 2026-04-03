from __future__ import annotations

from .helpers import semantic_gate_bucket

_FIXTURE_REWRITE_EXPECTATIONS: dict[str, dict[tuple[str, ...], object]] = {
    "demo.user.advanced.countUsersDirectFiltered#v3": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "WHERE_CLAUSE",
    },
    "demo.user.advanced.listUsersRecentPaged#v5": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "STATIC_INCLUDE_ONLY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.user.advanced.countUsersFilteredWrapped#v4": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_COUNT_WRAPPER",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): "DYNAMIC_COUNT_WRAPPER_COLLAPSE",
    },
    "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "STATIC_INCLUDE_ONLY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.user.advanced.listUsersFilteredWrapped#v15": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
    },
    "demo.user.advanced.listUsersRecentPagedWrapped#v16": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "STATIC_INCLUDE_ONLY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
    },
    "demo.user.advanced.listUsersFilteredAliased#v17": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    },
    "demo.user.advanced.listUsersFilteredQualifiedAliases#v22": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    },
    "demo.user.advanced.listUsersFilteredAliasedChoose#v23": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "REVIEW_REQUIRED",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "WHERE_CLAUSE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): None,
    },
    "demo.user.advanced.listUsersFilteredTableAliased#v18": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
    },
    "demo.user.advanced.listUsersFilteredPredicateAliased#v24": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "IF_GUARDED_FILTER_STATEMENT",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "patchSurface"): "STATEMENT_BODY",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "baselineFamily"): "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
    },
    "demo.order.harness.findOrdersByNos#v1": {
        ("rewriteFacts", "dynamicTemplate", "present"): True,
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "shapeFamily"): "FOREACH_IN_PREDICATE",
        ("rewriteFacts", "dynamicTemplate", "capabilityProfile", "capabilityTier"): "REVIEW_REQUIRED",
    },
    "demo.user.advanced.listDistinctUserStatuses#v11": {
        ("rewriteFacts", "aggregationQuery", "distinctPresent"): True,
        ("rewriteFacts", "aggregationQuery", "distinctRelaxationCandidate"): True,
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "shapeFamily"): "DISTINCT",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "constraintFamily"): "DISTINCT_RELAXATION",
    },
    "demo.order.harness.aggregateOrdersByStatus#v5": {
        ("rewriteFacts", "aggregationQuery", "groupByPresent"): True,
        ("rewriteFacts", "aggregationQuery", "groupByColumns"): ["status"],
        ("rewriteFacts", "aggregationQuery", "aggregateFunctions"): ["COUNT", "SUM"],
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "shapeFamily"): "GROUP_BY",
    },
    "demo.order.harness.aggregateOrdersByStatusWrapped#v9": {
        ("rewriteFacts", "aggregationQuery", "groupByPresent"): True,
        ("rewriteFacts", "aggregationQuery", "groupByColumns"): ["status"],
        ("rewriteFacts", "aggregationQuery", "aggregateFunctions"): ["COUNT", "SUM"],
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "safeBaselineFamily"): "REDUNDANT_GROUP_BY_WRAPPER",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.order.harness.listOrderUserCountsHaving#v8": {
        ("rewriteFacts", "aggregationQuery", "havingPresent"): True,
        ("rewriteFacts", "aggregationQuery", "havingExpression"): "COUNT(*) > 1",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "shapeFamily"): "HAVING",
    },
    "demo.order.harness.listOrderUserCountsHavingWrapped#v10": {
        ("rewriteFacts", "aggregationQuery", "groupByPresent"): True,
        ("rewriteFacts", "aggregationQuery", "havingPresent"): True,
        ("rewriteFacts", "aggregationQuery", "havingExpression"): "COUNT(*) > 1",
        ("rewriteFacts", "aggregationQuery", "aggregateFunctions"): ["COUNT"],
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "safeBaselineFamily"): "REDUNDANT_HAVING_WRAPPER",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.order.harness.aggregateOrdersByStatusAliased#v11": {
        ("rewriteFacts", "aggregationQuery", "groupByPresent"): True,
        ("rewriteFacts", "aggregationQuery", "groupByColumns"): ["o.status"],
        ("rewriteFacts", "aggregationQuery", "aggregateFunctions"): ["COUNT", "SUM"],
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "safeBaselineFamily"): "GROUP_BY_FROM_ALIAS_CLEANUP",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.order.harness.listOrderUserCountsHavingAliased#v12": {
        ("rewriteFacts", "aggregationQuery", "groupByPresent"): True,
        ("rewriteFacts", "aggregationQuery", "havingPresent"): True,
        ("rewriteFacts", "aggregationQuery", "groupByColumns"): ["o.user_id"],
        ("rewriteFacts", "aggregationQuery", "havingExpression"): "COUNT(*) > 1",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "safeBaselineFamily"): "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.user.advanced.listDistinctUserStatusesAliased#v19": {
        ("rewriteFacts", "aggregationQuery", "distinctPresent"): True,
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "safeBaselineFamily"): "DISTINCT_FROM_ALIAS_CLEANUP",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "capabilityTier"): "SAFE_BASELINE",
    },
    "demo.order.harness.listOrderAmountWindowRanks#v7": {
        ("rewriteFacts", "aggregationQuery", "windowPresent"): True,
        ("rewriteFacts", "aggregationQuery", "windowFunctions"): ["ROW_NUMBER"],
        ("rewriteFacts", "aggregationQuery", "orderByExpression"): None,
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "shapeFamily"): "WINDOW",
    },
    "demo.shipment.harness.listShipmentStatusUnion#v6": {
        ("rewriteFacts", "aggregationQuery", "unionPresent"): True,
        ("rewriteFacts", "aggregationQuery", "unionBranches"): 2,
        ("rewriteFacts", "aggregationQuery", "orderByExpression"): "status, id",
        ("rewriteFacts", "aggregationQuery", "capabilityProfile", "shapeFamily"): "UNION",
    },
}


def _nested_get(document: dict, path: tuple[str, ...]) -> object:
    current: object = document
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def assert_validate_matrix_matches_scenarios(
    scenarios: list[dict],
    acceptance_by_key: dict[str, dict],
) -> None:
    for scenario in scenarios:
        sql_key = str(scenario["sqlKey"])
        result = acceptance_by_key[sql_key]
        expected_status = str(scenario["targetValidateStatus"])
        actual_status = str(result["status"])
        if actual_status != expected_status:
            raise AssertionError(f"{sql_key}: expected validate status {expected_status!r}, got {actual_status!r}")

        expected_gate = str(scenario["targetSemanticGate"])
        actual_gate = semantic_gate_bucket(result)
        if actual_gate != expected_gate:
            raise AssertionError(f"{sql_key}: expected semantic gate {expected_gate!r}, got {actual_gate!r}")

        for path, expected_value in _FIXTURE_REWRITE_EXPECTATIONS.get(sql_key, {}).items():
            actual_value = _nested_get(result, path)
            if actual_value != expected_value:
                dotted_path = ".".join(path)
                raise AssertionError(
                    f"{sql_key}: expected {dotted_path}={expected_value!r}, got {actual_value!r}"
                )
