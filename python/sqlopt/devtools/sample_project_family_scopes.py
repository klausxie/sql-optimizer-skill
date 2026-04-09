from __future__ import annotations

IF_GUARDED_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersFilteredWrapped",
    "demo.user.advanced.listUsersFilteredAliased",
    "demo.user.advanced.listUsersFilteredQualifiedAliases",
    "demo.user.advanced.listUsersFilteredTableAliased",
    "demo.user.advanced.listUsersFilteredPredicateAliased",
    "demo.user.advanced.listUsersFilteredAliasedChoose",
    "demo.user.advanced.listUsersFilteredAliasedChooseContractBlocked",
    "demo.user.advanced.listUsersFilteredPredicateAliasedContractBlocked",
)
IF_GUARDED_COUNT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.countUsersWrapped",
    "demo.user.advanced.countUsersDirectFiltered",
    "demo.user.advanced.countUsersFilteredWrapped",
)
STATIC_INCLUDE_SAMPLE_SQL_KEYS = (
    "demo.user.listUsers",
    "demo.user.advanced.listUsersRecentPaged",
    "demo.user.advanced.listUsersViaStaticIncludeWrapped",
    "demo.user.advanced.listUsersRecentPagedWrapped",
)
STATIC_STATEMENT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersProjected",
    "demo.user.advanced.listUsersProjectedAliases",
    "demo.user.advanced.listUsersProjectedQualifiedAliases",
)
STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersProjectedAliases",
    "demo.user.advanced.listUsersProjectedQualifiedAliases",
)
GROUP_BY_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.order.harness.aggregateOrdersByStatus",
    "demo.order.harness.aggregateOrdersByStatusWrapped",
)
GROUP_BY_ALIAS_SAMPLE_SQL_KEYS = ("demo.order.harness.aggregateOrdersByStatusAliased",)
HAVING_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.order.harness.listOrderUserCountsHaving",
    "demo.order.harness.listOrderUserCountsHavingWrapped",
)
HAVING_ALIAS_SAMPLE_SQL_KEYS = ("demo.order.harness.listOrderUserCountsHavingAliased",)
STATIC_DISTINCT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listDistinctUserStatuses",
    "demo.user.advanced.listDistinctUserStatusesWrapped",
    "demo.user.advanced.listDistinctUserStatusesAliased",
)
DISTINCT_ALIAS_SAMPLE_SQL_KEYS = ("demo.user.advanced.listDistinctUserStatusesAliased",)
DISTINCT_WRAPPER_SAMPLE_SQL_KEYS = ("demo.user.advanced.listDistinctUserStatusesWrapped",)
ORDER_BY_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersOrderByConstant",)
OR_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersStatusOrPair",)
CASE_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersCaseWhenTrue",)
COALESCE_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersCoalesceIdentity",)
EXPRESSION_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersFoldedExpression",)
LIMIT_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersLargeLimit",)
NULL_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersEmailNullComparison",)
DISTINCT_ON_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersDistinctOnStatus",)
EXISTS_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersExistsSelfIdentity",)
UNION_COLLAPSE_SAMPLE_SQL_KEYS = ("demo.shipment.harness.listShipmentStatusUnionWrapped",)
BOOLEAN_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersBooleanTautology",)
IN_LIST_SAMPLE_SQL_KEYS = ("demo.user.advanced.listUsersStatusInSingle",)
STATIC_WRAPPER_SAMPLE_SQL_KEYS = ("demo.shipment.harness.listRecentShipmentsPaged",)
STATIC_UNION_SAMPLE_SQL_KEYS = ("demo.shipment.harness.listShipmentStatusUnion",)
STATIC_WINDOW_SAMPLE_SQL_KEYS = ("demo.order.harness.listOrderAmountWindowRanks",)
STATIC_CTE_SAMPLE_SQL_KEYS = ("demo.user.advanced.listRecentUsersViaCte",)
GENERALIZATION_BATCH1_SQL_KEYS = (
    "demo.user.findUsers",
    "demo.user.countUser",
    "demo.shipment.harness.findShipments",
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.test.complex.fromClauseSubquery",
)
GENERALIZATION_BATCH2_SQL_KEYS = (
    "demo.test.complex.wrapperCount",
    "demo.test.complex.multiFragmentLevel1",
    "demo.test.complex.staticSimpleSelect",
    "demo.test.complex.inSubquery",
    "demo.user.advanced.findUsersByKeyword",
)
GENERALIZATION_BATCH3_SQL_KEYS = (
    "demo.test.complex.includeSimple",
    "demo.test.complex.multiFragmentLevel2",
    "demo.test.complex.staticOrderBy",
    "demo.test.complex.existsSubquery",
    "demo.test.complex.leftJoinWithNull",
)
GENERALIZATION_BATCH4_SQL_KEYS = (
    "demo.order.harness.findOrdersByNos",
    "demo.order.harness.findOrdersByUserIdsAndStatus",
    "demo.shipment.harness.findShipmentsByOrderIds",
    "demo.test.complex.fragmentMultiplePlaces",
    "demo.test.complex.multiFragmentSeparate",
)
GENERALIZATION_BATCH5_SQL_KEYS = (
    "demo.user.advanced.findUsersByKeyword",
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.chooseWithLimit",
    "demo.test.complex.selectWithFragmentChoose",
)
GENERALIZATION_BATCH6_SQL_KEYS = (
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.shipment.harness.findShipments",
    "demo.test.complex.staticSimpleSelect",
    "demo.test.complex.inSubquery",
    "demo.test.complex.includeSimple",
)
GENERALIZATION_BATCH7_SQL_KEYS = (
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.shipment.harness.findShipments",
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.user.advanced.findUsersByKeyword",
)

GENERALIZATION_BATCH_SCOPE_SQL_KEYS = {
    "generalization-batch1": GENERALIZATION_BATCH1_SQL_KEYS,
    "generalization-batch2": GENERALIZATION_BATCH2_SQL_KEYS,
    "generalization-batch3": GENERALIZATION_BATCH3_SQL_KEYS,
    "generalization-batch4": GENERALIZATION_BATCH4_SQL_KEYS,
    "generalization-batch5": GENERALIZATION_BATCH5_SQL_KEYS,
    "generalization-batch6": GENERALIZATION_BATCH6_SQL_KEYS,
    "generalization-batch7": GENERALIZATION_BATCH7_SQL_KEYS,
}

FAMILY_SCOPE_SQL_KEYS = {
    "family": IF_GUARDED_SAMPLE_SQL_KEYS,
    "count-family": IF_GUARDED_COUNT_SAMPLE_SQL_KEYS,
    "include-family": STATIC_INCLUDE_SAMPLE_SQL_KEYS,
    "static-family": STATIC_STATEMENT_SAMPLE_SQL_KEYS,
    "alias-family": STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS,
    "groupby-family": GROUP_BY_WRAPPER_SAMPLE_SQL_KEYS,
    "groupby-alias-family": GROUP_BY_ALIAS_SAMPLE_SQL_KEYS,
    "having-family": HAVING_WRAPPER_SAMPLE_SQL_KEYS,
    "having-alias-family": HAVING_ALIAS_SAMPLE_SQL_KEYS,
    "distinct-family": STATIC_DISTINCT_SAMPLE_SQL_KEYS,
    "distinct-alias-family": DISTINCT_ALIAS_SAMPLE_SQL_KEYS,
    "distinct-wrapper-family": DISTINCT_WRAPPER_SAMPLE_SQL_KEYS,
    "orderby-family": ORDER_BY_SAMPLE_SQL_KEYS,
    "or-family": OR_SAMPLE_SQL_KEYS,
    "case-family": CASE_SAMPLE_SQL_KEYS,
    "coalesce-family": COALESCE_SAMPLE_SQL_KEYS,
    "expression-family": EXPRESSION_SAMPLE_SQL_KEYS,
    "limit-family": LIMIT_SAMPLE_SQL_KEYS,
    "null-family": NULL_SAMPLE_SQL_KEYS,
    "distinct-on-family": DISTINCT_ON_SAMPLE_SQL_KEYS,
    "exists-family": EXISTS_SAMPLE_SQL_KEYS,
    "union-collapse-family": UNION_COLLAPSE_SAMPLE_SQL_KEYS,
    "boolean-family": BOOLEAN_SAMPLE_SQL_KEYS,
    "in-list-family": IN_LIST_SAMPLE_SQL_KEYS,
    "wrapper-family": STATIC_WRAPPER_SAMPLE_SQL_KEYS,
    "union-family": STATIC_UNION_SAMPLE_SQL_KEYS,
    "window-family": STATIC_WINDOW_SAMPLE_SQL_KEYS,
    "cte-family": STATIC_CTE_SAMPLE_SQL_KEYS,
    **GENERALIZATION_BATCH_SCOPE_SQL_KEYS,
}
