from __future__ import annotations

import unittest

from sqlopt.devtools.harness.assertions import (
    assert_validate_matrix_matches_scenarios,
    fixture_registered_blocked_neighbor_families,
    fixture_registered_families,
    registered_patch_family_spec,
)
from sqlopt.devtools.harness.runtime import FIXTURE_PROJECT_ROOT, run_fixture_validate_harness
from sqlopt.devtools.harness.scenarios import (
    BLOCKER_FAMILIES,
    PATCHABILITY_TARGETS,
    SCENARIO_CLASSES,
    SEMANTIC_TARGETS,
    VALIDATE_EVIDENCE_MODES,
    VALIDATE_STATUSES,
    load_fixture_scenarios,
)
from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES


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
            self.assertTrue((FIXTURE_PROJECT_ROOT / str(scenario["mapperPath"])).exists())

    def test_fixture_project_validate_matches_scenario_matrix(self) -> None:
        scenarios, _proposals, _acceptance_rows, _units_by_key, acceptance_by_key, _fragment_catalog = run_fixture_validate_harness()
        assert_validate_matrix_matches_scenarios(scenarios, acceptance_by_key)


if __name__ == "__main__":
    unittest.main()
