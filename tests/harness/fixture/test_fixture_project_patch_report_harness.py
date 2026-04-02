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
            next_target_sql_key="demo.user.advanced.listDistinctUserStatuses#v11",
        )
        sql_rows = {str(row["sql_key"]): row for row in report_artifacts.diagnostics_sql_artifacts}
        self.assertEqual(sql_rows["demo.user.advanced.listUsersRecentPaged#v5"]["dynamic_shape_family"], "STATIC_INCLUDE_ONLY")
        self.assertEqual(sql_rows["demo.user.advanced.countUsersFilteredWrapped#v4"]["dynamic_shape_family"], "IF_GUARDED_COUNT_WRAPPER")
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersViaStaticIncludeWrapped#v14"]["dynamic_shape_family"],
            "STATIC_INCLUDE_ONLY",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredWrapped#v15"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersRecentPagedWrapped#v16"]["dynamic_shape_family"],
            "STATIC_INCLUDE_ONLY",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased#v17"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased#v17"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliased#v17"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases#v22"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases#v22"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredQualifiedAliases#v22"]["dynamic_delivery_class"],
            "SAFE_BASELINE_BLOCKED",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliasedChoose#v23"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredAliasedChoose#v23"]["dynamic_delivery_class"],
            "REVIEW_ONLY",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased#v18"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased#v18"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredTableAliased#v18"]["dynamic_delivery_class"],
            "READY_DYNAMIC_PATCH",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased#v24"]["dynamic_shape_family"],
            "IF_GUARDED_FILTER_STATEMENT",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased#v24"]["dynamic_baseline_family"],
            "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
        )
        self.assertEqual(
            sql_rows["demo.user.advanced.listUsersFilteredPredicateAliased#v24"]["dynamic_delivery_class"],
            "SAFE_BASELINE_BLOCKED",
        )
        self.assertEqual(sql_rows["demo.order.harness.findOrdersByNos#v1"]["dynamic_shape_family"], "FOREACH_IN_PREDICATE")
        self.assertEqual(
            sql_rows["demo.order.harness.findOrdersByNos#v1"]["dynamic_blocking_reason"],
            "FOREACH_INCLUDE_PREDICATE",
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
