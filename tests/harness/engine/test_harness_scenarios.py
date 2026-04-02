from __future__ import annotations

import unittest

from sqlopt.devtools.harness.scenarios import (
    calibrate_extension_scenarios,
    generate_extension_scenarios,
    load_scenarios,
    summarize_scenarios,
)


class HarnessScenariosTest(unittest.TestCase):
    def test_load_and_summarize_scenarios_use_sample_project_matrix(self) -> None:
        scenarios = load_scenarios()
        summary = summarize_scenarios(scenarios)

        self.assertGreaterEqual(len(scenarios), 20)
        self.assertEqual(summary["roadmapStageCounts"]["NEXT"], 1)
        self.assertIn("demo.user.advanced.listDistinctUserStatuses#v11", summary["nextTargetSqlKeys"])

    def test_generate_extension_scenarios_only_emits_new_complex_units(self) -> None:
        existing = [
            {
                "sqlKey": "demo.test.complex.existing#v1",
                "roadmapStage": "BASELINE",
            }
        ]
        units_by_key = {
            "demo.test.complex.existing#v1": {
                "statementType": "SELECT",
                "statementId": "existing",
                "dynamicFeatures": ["IF", "FOREACH"],
                "riskFlags": [],
                "xmlPath": "src/main/resources/com/example/mapper/test/complex_harness_mapper.xml",
            },
            "demo.test.complex.newDynamic#v1": {
                "statementType": "SELECT",
                "statementId": "newDynamic",
                "dynamicFeatures": ["IF", "FOREACH"],
                "riskFlags": [],
                "xmlPath": "src/main/resources/com/example/mapper/test/complex_harness_mapper.xml",
            },
            "demo.user.other#v1": {
                "statementType": "SELECT",
                "statementId": "other",
                "dynamicFeatures": [],
                "riskFlags": [],
                "xmlPath": "src/main/resources/com/example/mapper/user/user_mapper.xml",
            },
        }

        generated = generate_extension_scenarios(units_by_key, existing_scenarios=existing)

        self.assertEqual(len(generated), 1)
        row = generated[0]
        self.assertEqual(row["sqlKey"], "demo.test.complex.newDynamic#v1")
        self.assertEqual(row["roadmapStage"], "EXTENSION")
        self.assertEqual(row["roadmapTheme"], "COMPLEX_DYNAMIC")
        self.assertEqual(row["targetPatchability"], "REVIEW")
        self.assertEqual(row["targetBlockerFamily"], "TEMPLATE_UNSUPPORTED")

    def test_calibrate_extension_scenarios_updates_only_extension_rows(self) -> None:
        scenarios = [
            {
                "sqlKey": "demo.keep#v1",
                "roadmapStage": "BASELINE",
                "scenarioClass": "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
                "targetPatchReasonCode": "UNCHANGED",
                "targetPatchStrategy": None,
                "targetValidateStatus": "NEED_MORE_PARAMS",
                "targetSemanticGate": "UNCERTAIN",
                "targetPatchability": "REVIEW",
                "targetPrimaryBlocker": "SEMANTIC_GATE_UNCERTAIN",
                "targetBlockerFamily": "TEMPLATE_UNSUPPORTED",
            },
            {
                "sqlKey": "demo.ext#v1",
                "roadmapStage": "EXTENSION",
                "scenarioClass": "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
                "targetPatchReasonCode": "OLD",
                "targetPatchStrategy": None,
                "targetValidateStatus": "NEED_MORE_PARAMS",
                "targetSemanticGate": "UNCERTAIN",
                "targetPatchability": "REVIEW",
                "targetPrimaryBlocker": "SEMANTIC_GATE_UNCERTAIN",
                "targetBlockerFamily": "TEMPLATE_UNSUPPORTED",
            },
        ]
        acceptance_rows = [
            {
                "sqlKey": "demo.ext#v1",
                "status": "PASS",
                "semanticEquivalence": {"status": "PASS"},
            }
        ]
        patches = [
            {
                "sqlKey": "demo.ext#v1",
                "strategyType": "EXACT_TEMPLATE_EDIT",
                "selectionReason": {"code": "PATCH_READY_EXACT_TEMPLATE_EDIT"},
                "deliveryStage": "APPLY_READY",
                "applicable": True,
                "gates": {"semanticEquivalenceStatus": "PASS"},
            }
        ]

        calibrated = calibrate_extension_scenarios(
            scenarios,
            acceptance_rows=acceptance_rows,
            patches=patches,
        )

        self.assertEqual(calibrated[0]["targetPatchReasonCode"], "UNCHANGED")
        self.assertEqual(calibrated[1]["scenarioClass"], "PATCH_READY_STATEMENT")
        self.assertEqual(calibrated[1]["targetPatchStrategy"], "EXACT_TEMPLATE_EDIT")
        self.assertEqual(calibrated[1]["targetValidateStatus"], "PASS")
        self.assertEqual(calibrated[1]["targetSemanticGate"], "PASS")
        self.assertEqual(calibrated[1]["targetPatchability"], "READY")
        self.assertEqual(calibrated[1]["targetPrimaryBlocker"], None)
        self.assertEqual(calibrated[1]["targetBlockerFamily"], "READY")


if __name__ == "__main__":
    unittest.main()
