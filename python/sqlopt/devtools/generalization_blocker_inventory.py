from __future__ import annotations

READY_SENTINEL_SQL_KEYS = (
    "demo.test.complex.fromClauseSubquery",
    "demo.user.countUser",
    "demo.test.complex.wrapperCount",
)

CHOOSE_AWARE_PRIMARY_SENTINELS = (
    "demo.user.advanced.findUsersByKeyword",
)

CHOOSE_AWARE_GUARDRAIL_SENTINELS = (
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.chooseWithLimit",
    "demo.test.complex.selectWithFragmentChoose",
    "demo.order.harness.listOrdersWithUsersPaged",
)

COLLECTION_PREDICATE_PRIMARY_SENTINELS = (
    "demo.order.harness.findOrdersByUserIdsAndStatus",
)

COLLECTION_PREDICATE_GUARDRAIL_SENTINELS = (
    "demo.shipment.harness.findShipmentsByOrderIds",
    "demo.user.advanced.findUsersByKeyword",
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.test.complex.multiFragmentLevel1",
    "demo.shipment.harness.findShipments",
)

FRAGMENT_INCLUDE_PRIMARY_SENTINELS = (
    "demo.test.complex.multiFragmentLevel1",
)

FRAGMENT_INCLUDE_GUARDRAIL_SENTINELS = (
    "demo.test.complex.includeNested",
    "demo.test.complex.fragmentInJoin",
    "demo.test.complex.includeWithWhere",
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.user.advanced.findUsersByKeyword",
)

SEMANTIC_VALIDATION_PRIMARY_SENTINELS = (
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.test.complex.includeNested",
    "demo.user.findUsers",
)

SEMANTIC_VALIDATION_GUARDRAIL_SENTINELS = (
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.fragmentMultiplePlaces",
    "demo.test.complex.leftJoinWithNull",
    "demo.test.complex.existsSubquery",
)

UNSUPPORTED_STRATEGY_PRIMARY_SENTINELS = (
    "demo.test.complex.existsSubquery",
    "demo.test.complex.inSubquery",
    "demo.test.complex.leftJoinWithNull",
)

UNSUPPORTED_STRATEGY_GUARDRAIL_SENTINELS = (
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.test.complex.includeNested",
    "demo.user.findUsers",
    "demo.test.complex.staticSimpleSelect",
)

LOW_VALUE_PRIMARY_SENTINELS = (
    "demo.test.complex.staticSimpleSelect",
    "demo.test.complex.staticOrderBy",
)

LOW_VALUE_GUARDRAIL_SENTINELS = (
    "demo.test.complex.existsSubquery",
    "demo.test.complex.inSubquery",
    "demo.test.complex.leftJoinWithNull",
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.test.complex.includeNested",
    "demo.user.findUsers",
)

BLOCKED_BOUNDARY_SQL_KEYS = (
    "demo.order.harness.findOrdersByNos",
    "demo.shipment.harness.findShipmentsByOrderIds",
    "demo.test.complex.multiFragmentSeparate",
    "demo.test.complex.selectWithFragmentChoose",
)

LOW_VALUE_ONLY_CLUSTER = (
    "demo.test.complex.staticOrderBy",
    "demo.test.complex.staticSimpleSelect",
)

NO_SAFE_BASELINE_RECOVERY_CLUSTER = (
    "demo.order.harness.findOrdersByUserIdsAndStatus",
    "demo.shipment.harness.findShipments",
    "demo.test.complex.multiFragmentLevel1",
    "demo.user.advanced.findUsersByKeyword",
)

SEMANTIC_PREDICATE_CHANGED_CLUSTER = (
    "demo.order.harness.listOrdersWithUsersPaged",
)

SEMANTIC_ERROR_CLUSTER = (
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.chooseWithLimit",
    "demo.test.complex.fragmentMultiplePlaces",
    "demo.test.complex.selectWithFragmentChoose",
)

UNSUPPORTED_STRATEGY_CLUSTER = (
    "demo.test.complex.existsSubquery",
    "demo.test.complex.inSubquery",
    "demo.test.complex.leftJoinWithNull",
)

POST_BATCH7_SENTINELS = {
    "POST_BATCH7_CANDIDATE_TARGETS": (),
    "POST_BATCH7_SAFE_BASELINE_SENTINELS": (
        "demo.shipment.harness.findShipments",
        "demo.user.advanced.findUsersByKeyword",
    ),
    "POST_BATCH7_SEMANTIC_SENTINELS": (
        "demo.order.harness.listOrdersWithUsersPaged",
        "demo.test.complex.chooseBasic",
        "demo.test.complex.chooseMultipleWhen",
    ),
}

POST_BATCH8_SENTINELS = {
    "POST_BATCH8_SAFE_BASELINE_SENTINELS": (
        "demo.user.advanced.findUsersByKeyword",
        "demo.shipment.harness.findShipments",
        "demo.test.complex.multiFragmentLevel1",
    ),
    "POST_BATCH8_CANDIDATE_SENTINELS": (
        "demo.test.complex.inSubquery",
    ),
    "POST_BATCH8_SEMANTIC_SENTINELS": (
        "demo.order.harness.listOrdersWithUsersPaged",
    ),
}

POST_BATCH9_SENTINELS = {
    "POST_BATCH9_SAFE_BASELINE_SENTINELS": (
        "demo.user.advanced.findUsersByKeyword",
        "demo.shipment.harness.findShipments",
        "demo.test.complex.multiFragmentLevel1",
        "demo.order.harness.findOrdersByUserIdsAndStatus",
    ),
    "POST_BATCH9_SEMANTIC_SENTINELS": (
        "demo.order.harness.listOrdersWithUsersPaged",
    ),
}
