from __future__ import annotations

import unittest

from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES

from .fixture_project_harness_support import (
    BLOCKER_FAMILIES,
    FIXTURE_PROJECT,
    PATCHABILITY_TARGETS,
    SCENARIO_CLASSES,
    SEMANTIC_TARGETS,
    VALIDATE_EVIDENCE_MODES,
    VALIDATE_STATUSES,
    fixture_registered_blocked_neighbor_families,
    fixture_registered_families,
    load_fixture_scenarios,
    registered_patch_family_spec,
    run_fixture_validate_harness,
    semantic_gate_bucket,
)


class FixtureScenarioValidateHarnessTest(unittest.TestCase):
    def test_fixture_current_registered_family_surface_stays_backed_by_registry(self) -> None:
        scenarios = load_fixture_scenarios()
        registered_families = fixture_registered_families(scenarios)
        self.assertTrue(registered_families)
        for family in registered_families:
            spec = registered_patch_family_spec(family)
            self.assertIsNotNone(spec, family)
            self.assertTrue(spec.fixture_obligations.ready_case_required, family)

        required_blocked_neighbor_families = {
            family
            for family in registered_families
            if bool(registered_patch_family_spec(family).fixture_obligations.blocked_neighbor_required)
        }
        self.assertTrue(required_blocked_neighbor_families <= fixture_registered_blocked_neighbor_families(scenarios))

    def test_fixture_registered_blocked_neighbor_helper_excludes_ready_static_registered_rows(self) -> None:
        ready_only_scenarios = [
            {
                "sqlKey": "demo.user.advanced.listUsersProjectedAliases#v20",
                "scenarioClass": "PATCH_READY_STATEMENT",
                "targetPatchStrategy": "EXACT_TEMPLATE_EDIT",
                "targetRegisteredFamily": "STATIC_ALIAS_PROJECTION_CLEANUP",
            }
        ]
        self.assertEqual(fixture_registered_blocked_neighbor_families(ready_only_scenarios), set())

        scenarios = ready_only_scenarios + [
            {
                "sqlKey": "demo.user.advanced.listUsersProjectedQualifiedAliases#v21",
                "scenarioClass": "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
                "targetPatchStrategy": None,
                "targetRegisteredFamily": "STATIC_ALIAS_PROJECTION_CLEANUP",
            },
        ]

        blocked_neighbor_families = fixture_registered_blocked_neighbor_families(scenarios)
        self.assertEqual(blocked_neighbor_families, {"STATIC_ALIAS_PROJECTION_CLEANUP"})

    def test_fixture_ready_dynamic_baselines_stay_within_frozen_scope(self) -> None:
        scenarios = load_fixture_scenarios()
        ready_dynamic_families = {
            str(scenario["targetDynamicBaselineFamily"])
            for scenario in scenarios
            if str(scenario.get("targetDynamicDeliveryClass") or "").upper() == "READY_DYNAMIC_PATCH"
            and str(scenario.get("targetDynamicBaselineFamily") or "").strip()
        }
        self.assertTrue(ready_dynamic_families)
        self.assertTrue(ready_dynamic_families <= FROZEN_AUTO_PATCH_FAMILIES)

    def test_fixture_scenario_matrix_has_validate_harness_contract(self) -> None:
        scenarios = load_fixture_scenarios()
        self.assertGreaterEqual(len(scenarios), 20)
        for scenario in scenarios:
            self.assertIn(str(scenario["scenarioClass"]), SCENARIO_CLASSES)
            self.assertIn(str(scenario["validateEvidenceMode"]), VALIDATE_EVIDENCE_MODES)
            self.assertTrue(str(scenario["validateCandidateSql"]).strip())
            self.assertIn(str(scenario["targetValidateStatus"]), VALIDATE_STATUSES)
            self.assertIn(str(scenario["targetSemanticGate"]), SEMANTIC_TARGETS)
            self.assertIn(str(scenario["targetPatchability"]), PATCHABILITY_TARGETS)
            self.assertTrue(str(scenario["targetPatchReasonCode"]).strip())
            self.assertIn(str(scenario["targetBlockerFamily"]), BLOCKER_FAMILIES)
            self.assertTrue((FIXTURE_PROJECT / str(scenario["mapperPath"])).exists())

    def test_fixture_project_validate_matches_scenario_matrix(self) -> None:
        scenarios, _proposals, _acceptance_rows, _units_by_key, acceptance_by_key, _fragment_catalog = run_fixture_validate_harness()

        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            result = acceptance_by_key[sql_key]
            self.assertEqual(str(result["status"]), str(scenario["targetValidateStatus"]), sql_key)
            self.assertEqual(semantic_gate_bucket(result), str(scenario["targetSemanticGate"]), sql_key)
            rewrite_facts = result.get("rewriteFacts") or {}
            dynamic_template = rewrite_facts.get("dynamicTemplate") or {}
            aggregation_query = rewrite_facts.get("aggregationQuery") or {}
            capability_profile = aggregation_query.get("capabilityProfile") or {}
            dynamic_profile = dynamic_template.get("capabilityProfile") or {}
            if sql_key == "demo.user.advanced.countUsersDirectFiltered#v3":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "WHERE_CLAUSE", sql_key)
            if sql_key == "demo.user.advanced.listUsersRecentPaged#v5":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "STATIC_INCLUDE_ONLY", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.user.advanced.countUsersFilteredWrapped#v4":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_COUNT_WRAPPER", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
                self.assertEqual(dynamic_profile.get("baselineFamily"), "DYNAMIC_COUNT_WRAPPER_COLLAPSE", sql_key)
            if sql_key == "demo.user.advanced.listUsersViaStaticIncludeWrapped#v14":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "STATIC_INCLUDE_ONLY", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredWrapped#v15":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
            if sql_key == "demo.user.advanced.listUsersRecentPagedWrapped#v16":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "STATIC_INCLUDE_ONLY", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredAliased#v17":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
                self.assertEqual(dynamic_profile.get("baselineFamily"), "DYNAMIC_FILTER_SELECT_LIST_CLEANUP", sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredQualifiedAliases#v22":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
                self.assertEqual(dynamic_profile.get("baselineFamily"), "DYNAMIC_FILTER_SELECT_LIST_CLEANUP", sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredAliasedChoose#v23":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "REVIEW_REQUIRED", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "WHERE_CLAUSE", sql_key)
                self.assertIsNone(dynamic_profile.get("baselineFamily"), sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredTableAliased#v18":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
                self.assertEqual(dynamic_profile.get("baselineFamily"), "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP", sql_key)
            if sql_key == "demo.user.advanced.listUsersFilteredPredicateAliased#v24":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "IF_GUARDED_FILTER_STATEMENT", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
                self.assertEqual(dynamic_profile.get("patchSurface"), "STATEMENT_BODY", sql_key)
                self.assertEqual(dynamic_profile.get("baselineFamily"), "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP", sql_key)
            if sql_key == "demo.order.harness.findOrdersByNos#v1":
                self.assertEqual(dynamic_template.get("present"), True, sql_key)
                self.assertEqual(dynamic_profile.get("shapeFamily"), "FOREACH_IN_PREDICATE", sql_key)
                self.assertEqual(dynamic_profile.get("capabilityTier"), "REVIEW_REQUIRED", sql_key)
            if sql_key == "demo.user.advanced.listDistinctUserStatuses#v11":
                self.assertEqual(aggregation_query.get("distinctPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("distinctRelaxationCandidate"), True, sql_key)
                self.assertEqual(capability_profile.get("shapeFamily"), "DISTINCT", sql_key)
                self.assertEqual(capability_profile.get("constraintFamily"), "DISTINCT_RELAXATION", sql_key)
            if sql_key == "demo.order.harness.aggregateOrdersByStatus#v5":
                self.assertEqual(aggregation_query.get("groupByPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("groupByColumns"), ["status"], sql_key)
                self.assertEqual(aggregation_query.get("aggregateFunctions"), ["COUNT", "SUM"], sql_key)
                self.assertEqual(capability_profile.get("shapeFamily"), "GROUP_BY", sql_key)
            if sql_key == "demo.order.harness.aggregateOrdersByStatusWrapped#v9":
                self.assertEqual(aggregation_query.get("groupByPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("groupByColumns"), ["status"], sql_key)
                self.assertEqual(aggregation_query.get("aggregateFunctions"), ["COUNT", "SUM"], sql_key)
                self.assertEqual(capability_profile.get("safeBaselineFamily"), "REDUNDANT_GROUP_BY_WRAPPER", sql_key)
                self.assertEqual(capability_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.order.harness.listOrderUserCountsHaving#v8":
                self.assertEqual(aggregation_query.get("havingPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("havingExpression"), "COUNT(*) > 1", sql_key)
                self.assertEqual(capability_profile.get("shapeFamily"), "HAVING", sql_key)
            if sql_key == "demo.order.harness.listOrderUserCountsHavingWrapped#v10":
                self.assertEqual(aggregation_query.get("groupByPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("havingPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("havingExpression"), "COUNT(*) > 1", sql_key)
                self.assertEqual(aggregation_query.get("aggregateFunctions"), ["COUNT"], sql_key)
                self.assertEqual(capability_profile.get("safeBaselineFamily"), "REDUNDANT_HAVING_WRAPPER", sql_key)
                self.assertEqual(capability_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.order.harness.aggregateOrdersByStatusAliased#v11":
                self.assertEqual(aggregation_query.get("groupByPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("groupByColumns"), ["o.status"], sql_key)
                self.assertEqual(aggregation_query.get("aggregateFunctions"), ["COUNT", "SUM"], sql_key)
                self.assertEqual(capability_profile.get("safeBaselineFamily"), "GROUP_BY_FROM_ALIAS_CLEANUP", sql_key)
                self.assertEqual(capability_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.order.harness.listOrderUserCountsHavingAliased#v12":
                self.assertEqual(aggregation_query.get("groupByPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("havingPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("groupByColumns"), ["o.user_id"], sql_key)
                self.assertEqual(aggregation_query.get("havingExpression"), "COUNT(*) > 1", sql_key)
                self.assertEqual(capability_profile.get("safeBaselineFamily"), "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP", sql_key)
                self.assertEqual(capability_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.user.advanced.listDistinctUserStatusesAliased#v19":
                self.assertEqual(aggregation_query.get("distinctPresent"), True, sql_key)
                self.assertEqual(capability_profile.get("safeBaselineFamily"), "DISTINCT_FROM_ALIAS_CLEANUP", sql_key)
                self.assertEqual(capability_profile.get("capabilityTier"), "SAFE_BASELINE", sql_key)
            if sql_key == "demo.order.harness.listOrderAmountWindowRanks#v7":
                self.assertEqual(aggregation_query.get("windowPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("windowFunctions"), ["ROW_NUMBER"], sql_key)
                self.assertIsNone(aggregation_query.get("orderByExpression"), sql_key)
                self.assertEqual(capability_profile.get("shapeFamily"), "WINDOW", sql_key)
            if sql_key == "demo.shipment.harness.listShipmentStatusUnion#v6":
                self.assertEqual(aggregation_query.get("unionPresent"), True, sql_key)
                self.assertEqual(aggregation_query.get("unionBranches"), 2, sql_key)
                self.assertEqual(aggregation_query.get("orderByExpression"), "status, id", sql_key)
                self.assertEqual(capability_profile.get("shapeFamily"), "UNION", sql_key)


if __name__ == "__main__":
    unittest.main()
