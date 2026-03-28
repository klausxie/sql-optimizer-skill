from __future__ import annotations

import unittest
from pathlib import Path

from .fixture_project_harness_support import (
    BLOCKER_FAMILIES,
    FIXTURE_PROJECT,
    PATCHABILITY_TARGETS,
    ROADMAP_STAGES,
    ROADMAP_THEMES,
    SCENARIO_CLASSES,
    SEMANTIC_TARGETS,
    VALIDATE_EVIDENCE_MODES,
    VALIDATE_STATUSES,
    load_fixture_scenarios,
    scan_fixture_project,
    summarize_fixture_scenarios,
)


class FixtureScenarioMatrixTest(unittest.TestCase):
    def test_fixture_scenario_matrix_is_well_formed(self) -> None:
        scenarios = load_fixture_scenarios()
        self.assertGreaterEqual(len(scenarios), 20)
        required_fields = {
            "sqlKey",
            "statementType",
            "mapperPath",
            "domain",
            "scenarioClass",
            "purpose",
            "expectedScanFeatures",
            "expectedRiskFlags",
            "validateCandidateSql",
            "validateEvidenceMode",
            "targetValidateStatus",
            "targetSemanticGate",
            "targetPatchability",
            "targetPatchStrategy",
            "targetPatchReasonCode",
            "targetPrimaryBlocker",
            "targetBlockerFamily",
            "roadmapStage",
            "roadmapTheme",
            "targetPatchMustContain",
            "targetPatchMustNotContain",
        }

        sql_keys: set[str] = set()
        domains: set[str] = set()
        scenario_classes: set[str] = set()
        for scenario in scenarios:
            self.assertTrue(required_fields.issubset(set(scenario.keys())))
            sql_key = str(scenario["sqlKey"])
            self.assertNotIn(sql_key, sql_keys)
            sql_keys.add(sql_key)
            domains.add(str(scenario["domain"]))
            scenario_classes.add(str(scenario["scenarioClass"]))
            self.assertIn(str(scenario["scenarioClass"]), SCENARIO_CLASSES)
            self.assertTrue(str(scenario["validateCandidateSql"]).strip())
            self.assertIn(str(scenario["validateEvidenceMode"]), VALIDATE_EVIDENCE_MODES)
            self.assertIn(str(scenario["targetValidateStatus"]), VALIDATE_STATUSES)
            self.assertIn(str(scenario["targetSemanticGate"]), SEMANTIC_TARGETS)
            self.assertIn(str(scenario["targetPatchability"]), PATCHABILITY_TARGETS)
            self.assertIn(str(scenario["targetBlockerFamily"]), BLOCKER_FAMILIES)
            self.assertIn(str(scenario["roadmapStage"]), ROADMAP_STAGES)
            self.assertIn(str(scenario["roadmapTheme"]), ROADMAP_THEMES)
            self.assertIsInstance(scenario["expectedScanFeatures"], list)
            self.assertIsInstance(scenario["expectedRiskFlags"], list)
            self.assertIsInstance(scenario["targetPatchMustContain"], list)
            self.assertIsInstance(scenario["targetPatchMustNotContain"], list)
            mapper_path = FIXTURE_PROJECT / str(scenario["mapperPath"])
            self.assertTrue(mapper_path.exists(), mapper_path)

        self.assertEqual(domains, {"user", "order", "shipment", "test.complex"})
        self.assertEqual(scenario_classes, SCENARIO_CLASSES)
        summary = summarize_fixture_scenarios(scenarios)
        self.assertEqual(summary["roadmapStageCounts"]["NEXT"], 1)
        self.assertIn("demo.user.advanced.listDistinctUserStatuses#v11", summary["nextTargetSqlKeys"])
        self.assertEqual(summary["roadmapThemeCounts"]["CTE_ENABLEMENT"], 1)


class FixtureProjectScanHarnessTest(unittest.TestCase):
    def test_fixture_project_scan_matches_scenario_matrix(self) -> None:
        scenarios = load_fixture_scenarios()
        expected_by_key = {str(row["sqlKey"]): row for row in scenarios}
        _units, actual_by_key, _fragment_catalog = scan_fixture_project()
        self.assertEqual(set(actual_by_key), set(expected_by_key))

        for sql_key, scenario in expected_by_key.items():
            row = actual_by_key[sql_key]
            self.assertEqual(str(row["statementType"]), str(scenario["statementType"]))
            self.assertEqual(
                Path(str(row["xmlPath"])).resolve(),
                (FIXTURE_PROJECT / str(scenario["mapperPath"])).resolve(),
            )
            self.assertEqual(set(row.get("dynamicFeatures") or []), set(scenario["expectedScanFeatures"]))
            self.assertEqual(set(row.get("riskFlags") or []), set(scenario["expectedRiskFlags"]))
            if scenario["expectedScanFeatures"]:
                self.assertIsNotNone(row.get("dynamicTrace"), sql_key)
            if "INCLUDE" in set(scenario["expectedScanFeatures"]):
                self.assertGreater(len(row.get("includeTrace") or []), 0, sql_key)


if __name__ == "__main__":
    unittest.main()
