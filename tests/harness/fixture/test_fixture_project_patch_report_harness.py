from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from sqlopt.devtools.harness.assertions import (
    assert_auto_patches_frozen_and_verified,
    assert_fixture_scenario_summary,
    patch_apply_ready,
    assert_patch_matrix_matches_scenarios,
    assert_registered_fixture_patch_obligations,
)
from sqlopt.devtools.harness.runtime import (
    FIXTURE_PROJECT_ROOT,
    run_fixture_patch_and_report_harness,
)
from sqlopt.devtools.harness.scenarios import summarize_fixture_scenarios


class FixtureScenarioPatchReportHarnessTest(unittest.TestCase):
    def test_current_registered_fixture_patch_families_meet_registry_obligations(self) -> None:
        scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        assert_registered_fixture_patch_obligations(scenarios, patches)

    def test_auto_patches_require_frozen_family_and_replay_evidence(self) -> None:
        _scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        assert_auto_patches_frozen_and_verified(patches)

    def test_fixture_project_patch_matches_scenario_matrix(self) -> None:
        scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        assert_patch_matrix_matches_scenarios(scenarios, patches)

    def test_fixture_project_report_matches_matrix_aggregates(self) -> None:
        scenarios, _proposals, acceptance_rows, patches, report_artifacts = run_fixture_patch_and_report_harness()
        scenario_by_key = {str(row["sqlKey"]): row for row in scenarios}
        expected_batch6_blockers = {
            "demo.order.harness.listOrdersWithUsersPaged": "VALIDATE_SEMANTIC_ERROR",
            "demo.shipment.harness.findShipments": "VALIDATE_SEMANTIC_ERROR",
            "demo.test.complex.staticSimpleSelect": "NO_SAFE_BASELINE_RECOVERY",
            "demo.test.complex.inSubquery": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
            "demo.test.complex.includeSimple": "NO_PATCHABLE_CANDIDATE_LOW_VALUE_ONLY",
        }
        for sql_key, expected_blocker in expected_batch6_blockers.items():
            self.assertEqual(scenario_by_key[sql_key]["targetPrimaryBlocker"], expected_blocker)

        expected_boundary_blockers = {
            "demo.order.harness.findOrdersByNos": "VALIDATE_SEMANTIC_ERROR",
            "demo.shipment.harness.findShipmentsByOrderIds": "VALIDATE_SEMANTIC_ERROR",
            "demo.test.complex.multiFragmentSeparate": "VALIDATE_SEMANTIC_ERROR",
            "demo.test.complex.selectWithFragmentChoose": "VALIDATE_SEMANTIC_ERROR",
            "demo.test.complex.existsSubquery": "SEMANTIC_GATE_BLOCKED",
            "demo.test.complex.leftJoinWithNull": "SEMANTIC_GATE_BLOCKED",
            "demo.test.complex.chooseWithLimit": "VALIDATE_SEMANTIC_ERROR",
        }
        for sql_key, expected_blocker in expected_boundary_blockers.items():
            self.assertEqual(scenario_by_key[sql_key]["targetPrimaryBlocker"], expected_blocker)
        stats = report_artifacts.report.stats
        summary = summarize_fixture_scenarios(scenarios)
        expected_patch_ready = sum(1 for row in scenarios if row["targetPatchStrategy"])
        expected_blocked_sql_count = sum(
            1
            for row in scenarios
            if str(row["targetValidateStatus"]).upper() != "PASS"
            or str(row["targetSemanticGate"]).upper() != "PASS"
        )
        self.assertEqual(stats["sql_units"], len(scenarios))
        self.assertEqual(stats["patch_files"], expected_patch_ready)
        self.assertEqual(stats["patch_applicable_count"], expected_patch_ready)
        self.assertEqual(stats["blocked_sql_count"], expected_blocked_sql_count)
        self.assertEqual(len(acceptance_rows), len(scenarios))
        self.assertEqual(report_artifacts.report.to_contract()["phase_status"]["report"], "DONE")
        self.assertIn(report_artifacts.report.to_contract()["next_action"], {"apply", "inspect"})
        self.assertTrue(set(stats["blocker_family_counts"]).issubset({"READY", "SECURITY", "SEMANTIC", "TEMPLATE_UNSUPPORTED"}))
        assert_fixture_scenario_summary(
            summary,
            next_count=1,
            next_target_sql_key="demo.user.advanced.listDistinctUserStatuses",
        )
        sql_rows = {str(row["sql_key"]): row for row in report_artifacts.diagnostics_sql_artifacts}
        self.assertEqual(sql_rows["demo.user.advanced.listUsersRecentPaged"]["dynamic_shape_family"], "STATIC_INCLUDE_ONLY")
        self.assertEqual(sql_rows["demo.user.advanced.countUsersFilteredWrapped"]["dynamic_shape_family"], "IF_GUARDED_COUNT_WRAPPER")
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersViaStaticIncludeWrapped"]["dynamic_shape_family"],
            "STATIC_INCLUDE_ONLY",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredWrapped"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersRecentPagedWrapped"]["dynamic_shape_family"],
            "STATIC_INCLUDE_ONLY",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliasedChoose"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliasedChoose"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(sql_rows["demo.order.harness.findOrdersByNos"]["dynamic_shape_family"], "FOREACH_IN_PREDICATE")
        self.assertEqual(
            sql_rows["demo.order.harness.findOrdersByNos"]["dynamic_blocking_reason"],
            "FOREACH_INCLUDE_PREDICATE",
        )
        self.assertEqual(sql_rows["demo.shipment.harness.findShipmentsByOrderIds"]["dynamic_shape_family"], "FOREACH_IN_PREDICATE")
        self.assertEqual(
            sql_rows["demo.shipment.harness.findShipmentsByOrderIds"]["dynamic_blocking_reason"],
            "FOREACH_INCLUDE_PREDICATE",
        )
        self.assertEqual(
            sql_rows["demo.test.complex.multiFragmentSeparate"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.test.complex.multiFragmentSeparate"]["dynamic_blocking_reason"],
            "DYNAMIC_FILTER_SUBTREE",
        )
        self.assertEqual(
            sql_rows["demo.test.complex.selectWithFragmentChoose"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.test.complex.selectWithFragmentChoose"]["dynamic_blocking_reason"],
            "DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE",
        )
        self.assertEqual(sql_rows["demo.test.complex.existsSubquery"]["dynamic_shape_family"], "NONE")
        self.assertIsNone(sql_rows["demo.test.complex.existsSubquery"]["dynamic_blocking_reason"])
        self.assertEqual(sql_rows["demo.test.complex.leftJoinWithNull"]["dynamic_shape_family"], "NONE")
        self.assertIsNone(sql_rows["demo.test.complex.leftJoinWithNull"]["dynamic_blocking_reason"])
        self.assertEqual(
            sql_rows["demo.test.complex.chooseWithLimit"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.test.complex.chooseWithLimit"]["dynamic_blocking_reason"],
            "DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE",
        )

    def test_fixture_patch_harness_uses_temp_project_copy_as_apply_check_root(self) -> None:
        seen_cwds: list[Path] = []

        def _completed_process(*_args: object, **kwargs: object):
            cwd = kwargs.get("cwd")
            if cwd is not None:
                seen_cwds.append(Path(str(cwd)).resolve())
            from subprocess import CompletedProcess

            return CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")

        with patch("sqlopt.stages.patch_generate.subprocess.run", side_effect=_completed_process):
            _scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()

        self.assertTrue(any(patch_apply_ready(row) for row in patches))
        self.assertTrue(seen_cwds)
        self.assertEqual(len(set(seen_cwds)), 1)
        apply_root = seen_cwds[0]
        self.assertNotEqual(apply_root, FIXTURE_PROJECT_ROOT.resolve())
        self.assertEqual(apply_root.name, "sample_project")


if __name__ == "__main__":
    unittest.main()
