from __future__ import annotations

READY_SENTINEL_SQL_KEYS = (
    "demo.test.complex.fromClauseSubquery",
    "demo.user.countUser",
    "demo.test.complex.wrapperCount",
)

BLOCKED_BOUNDARY_SQL_KEYS = (
    "demo.order.harness.findOrdersByNos",
    "demo.shipment.harness.findShipmentsByOrderIds",
    "demo.test.complex.multiFragmentSeparate",
    "demo.test.complex.selectWithFragmentChoose",
)

LOW_VALUE_ONLY_CLUSTER = (
    "demo.order.harness.findOrdersByUserIdsAndStatus",
    "demo.order.harness.listOrdersWithUsersPaged",
    "demo.shipment.harness.findShipments",
    "demo.test.complex.chooseMultipleWhen",
    "demo.test.complex.inSubquery",
    "demo.test.complex.multiFragmentLevel1",
    "demo.test.complex.multiFragmentLevel2",
    "demo.test.complex.staticOrderBy",
    "demo.user.advanced.findUsersByKeyword",
)

NO_SAFE_BASELINE_RECOVERY_CLUSTER = (
    "demo.test.complex.includeSimple",
    "demo.test.complex.staticSimpleSelect",
)

SEMANTIC_ERROR_CLUSTER = (
    "demo.test.complex.chooseBasic",
    "demo.test.complex.chooseWithLimit",
    "demo.test.complex.fragmentMultiplePlaces",
)

UNSUPPORTED_STRATEGY_CLUSTER = (
    "demo.test.complex.existsSubquery",
    "demo.test.complex.leftJoinWithNull",
)

POST_BATCH7_SENTINELS = {
    "POST_BATCH7_CANDIDATE_TARGETS": (
        "demo.user.advanced.findUsersByKeyword",
    ),
    "POST_BATCH7_SAFE_BASELINE_SENTINELS": (
        "demo.shipment.harness.findShipments",
    ),
    "POST_BATCH7_SEMANTIC_SENTINELS": (
        "demo.order.harness.listOrdersWithUsersPaged",
        "demo.test.complex.chooseBasic",
        "demo.test.complex.chooseMultipleWhen",
    ),
}
