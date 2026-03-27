from __future__ import annotations

from collections import Counter
import unittest

from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES

from .fixture_project_harness_support import (
    fixture_registered_families,
    patch_apply_ready,
    patch_blocker_family,
    patch_meets_registered_fixture_obligations,
    run_fixture_patch_and_report_harness,
    summarize_fixture_scenarios,
)


class FixtureScenarioPatchReportHarnessTest(unittest.TestCase):
    @staticmethod
    def _expected_dynamic_summary(acceptance_row: dict, patch_row: dict) -> tuple[str | None, str | None]:
        dynamic_facts = dict((((acceptance_row.get("rewriteFacts") or {}).get("dynamicTemplate")) or {}))
        profile = dict((dynamic_facts.get("capabilityProfile") or {}) or {})
        if not dynamic_facts:
            return None, None
        baseline_family = str(profile.get("baselineFamily") or "").strip() or None
        capability_tier = str(profile.get("capabilityTier") or "").strip().upper()
        shape_family = str(profile.get("shapeFamily") or "").strip()
        blocking_reason = (
            str(patch_row.get("dynamicTemplateBlockingReason") or "").strip().upper()
            or str(profile.get("blockerFamily") or "").strip().upper()
            or None
        )
        strategy_type = str((patch_row.get("dynamicTemplateStrategy") or patch_row.get("strategyType") or "")).strip().upper()
        delivery_class = None
        if strategy_type.startswith("DYNAMIC_") and patch_apply_ready(patch_row):
            delivery_class = "READY_DYNAMIC_PATCH"
        elif capability_tier == "SAFE_BASELINE" and blocking_reason and blocking_reason.endswith("NO_EFFECTIVE_DIFF"):
            delivery_class = "SAFE_BASELINE_NO_DIFF"
        elif capability_tier == "SAFE_BASELINE":
            delivery_class = "SAFE_BASELINE_BLOCKED"
        elif shape_family:
            delivery_class = "REVIEW_ONLY"
        return baseline_family, delivery_class

    def test_current_registered_fixture_patch_families_meet_registry_obligations(self) -> None:
        scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        patch_by_key = {str(row["sqlKey"]): row for row in patches}
        registered_families = fixture_registered_families(scenarios)

        self.assertTrue(registered_families)
        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            patch = patch_by_key[sql_key]
            target_registered_family = str(scenario.get("targetRegisteredFamily") or "").strip()
            target_dynamic_family = str(scenario.get("targetDynamicBaselineFamily") or "").strip()
            tracked_family = target_registered_family or target_dynamic_family
            if not tracked_family:
                continue
            self.assertIn(tracked_family, registered_families, sql_key)
            self.assertTrue(patch_meets_registered_fixture_obligations(patch, scenario), sql_key)
            if target_registered_family and patch_apply_ready(patch):
                self.assertEqual(patch.get("patchFamily"), target_registered_family, sql_key)
            if str(scenario.get("targetDynamicDeliveryClass") or "").upper() == "READY_DYNAMIC_PATCH":
                self.assertEqual(patch.get("patchFamily"), target_dynamic_family, sql_key)

    def test_auto_patches_require_frozen_family_and_replay_evidence(self) -> None:
        _scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()

        auto_patches = [row for row in patches if patch_apply_ready(row)]
        self.assertTrue(auto_patches)
        for patch in auto_patches:
            sql_key = str(patch["sqlKey"])
            family = str(patch.get("patchFamily") or "").strip()
            self.assertIn(family, FROZEN_AUTO_PATCH_FAMILIES, sql_key)
            self.assertTrue(((patch.get("replayEvidence") or {}).get("matchesTarget")) is True, sql_key)
            self.assertTrue(((patch.get("syntaxEvidence") or {}).get("ok")) is True, sql_key)

    def test_fixture_project_patch_matches_scenario_matrix(self) -> None:
        scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        patch_by_key = {str(row["sqlKey"]): row for row in patches}

        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            patch = patch_by_key[sql_key]
            self.assertEqual(((patch.get("selectionReason") or {}).get("code")), scenario["targetPatchReasonCode"], sql_key)
            self.assertEqual(patch.get("strategyType"), scenario["targetPatchStrategy"], sql_key)
            self.assertEqual(patch_blocker_family(patch), str(scenario["targetBlockerFamily"]), sql_key)
            if scenario["targetPatchStrategy"]:
                self.assertTrue(patch.get("patchFiles"), sql_key)
                self.assertTrue(patch_apply_ready(patch), sql_key)
                patch_text = "\n".join(str(x) for x in (patch.get("_patchTexts") or []))
                added_text = "\n".join(
                    line[1:]
                    for line in patch_text.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
                for snippet in scenario["targetPatchMustContain"]:
                    self.assertIn(str(snippet), added_text, sql_key)
                for snippet in scenario["targetPatchMustNotContain"]:
                    self.assertNotIn(str(snippet), added_text, sql_key)
            else:
                self.assertEqual(patch.get("patchFiles"), [], sql_key)
                self.assertFalse(patch_apply_ready(patch), sql_key)

    def test_fixture_project_report_matches_matrix_aggregates(self) -> None:
        scenarios, _proposals, acceptance_rows, patches, report_artifacts = run_fixture_patch_and_report_harness()
        stats = report_artifacts.report.stats
        summary = summarize_fixture_scenarios(scenarios)
        scenario_by_key = {str(row["sqlKey"]): row for row in scenarios}
        patch_by_key = {str(row["sqlKey"]): row for row in patches}

        expected_status_counts = Counter(str(row["targetValidateStatus"]) for row in scenarios)
        expected_patch_ready = sum(1 for row in scenarios if row["targetPatchStrategy"])
        expected_strategy_counts = Counter(str(row["targetPatchStrategy"]) for row in scenarios if row["targetPatchStrategy"])
        expected_security_count = sum(1 for row in scenarios if row["scenarioClass"] == "PATCH_BLOCKED_SECURITY")
        expected_wrapper_count = sum(1 for row in scenarios if row["targetPatchStrategy"] == "SAFE_WRAPPER_COLLAPSE")
        expected_blocked_sql_count = sum(
            1
            for row in scenarios
            if str(row["targetValidateStatus"]).upper() != "PASS"
            or str(row["targetSemanticGate"]).upper() != "PASS"
        )
        expected_family_counts = Counter(str(row["targetBlockerFamily"]) for row in scenarios)
        expected_aggregation_shape_counts = Counter()
        expected_aggregation_constraint_counts = Counter()
        expected_aggregation_safe_baseline_counts = Counter()
        expected_aggregation_ready_family_counts = Counter()
        expected_aggregation_ready_patch_count = 0
        expected_dynamic_baseline_family_counts = Counter()
        expected_dynamic_delivery_class_counts = Counter()
        expected_dynamic_ready_baseline_family_counts = Counter()
        expected_dynamic_ready_patch_count = 0
        expected_dynamic_safe_baseline_blocked_count = 0
        expected_dynamic_review_only_count = 0
        for row in acceptance_rows:
            profile = ((((row.get("rewriteFacts") or {}).get("aggregationQuery") or {}).get("capabilityProfile")) or {})
            shape = str(profile.get("shapeFamily") or "").strip().upper()
            if shape and shape != "NONE":
                expected_aggregation_shape_counts[shape] += 1
            constraint = str(profile.get("constraintFamily") or "").strip().upper()
            if constraint and constraint != "NONE":
                expected_aggregation_constraint_counts[constraint] += 1
            safe_baseline = str(profile.get("safeBaselineFamily") or "").strip()
            if safe_baseline:
                expected_aggregation_safe_baseline_counts[safe_baseline] += 1
                if str(scenario_by_key[str(row["sqlKey"])]["targetPatchStrategy"] or "").strip() == "EXACT_TEMPLATE_EDIT":
                    expected_aggregation_ready_patch_count += 1
                    expected_aggregation_ready_family_counts[safe_baseline] += 1
            dynamic_baseline_family, dynamic_delivery_class = self._expected_dynamic_summary(
                row,
                patch_by_key[str(row["sqlKey"])],
            )
            if dynamic_baseline_family:
                expected_dynamic_baseline_family_counts[str(dynamic_baseline_family)] += 1
            if dynamic_delivery_class:
                expected_dynamic_delivery_class_counts[str(dynamic_delivery_class)] += 1
                normalized_dynamic_delivery_class = str(dynamic_delivery_class).upper()
                if normalized_dynamic_delivery_class == "READY_DYNAMIC_PATCH":
                    expected_dynamic_ready_patch_count += 1
                    if dynamic_baseline_family:
                        expected_dynamic_ready_baseline_family_counts[str(dynamic_baseline_family)] += 1
                elif normalized_dynamic_delivery_class in {"SAFE_BASELINE_BLOCKED", "SAFE_BASELINE_NO_DIFF"}:
                    expected_dynamic_safe_baseline_blocked_count += 1
                elif normalized_dynamic_delivery_class == "REVIEW_ONLY":
                    expected_dynamic_review_only_count += 1
        actual_family_counts = Counter(patch_blocker_family(row) for row in report_artifacts.report.items.patches)

        self.assertEqual(stats["sql_units"], len(scenarios))
        self.assertEqual(stats["acceptance_pass"], expected_status_counts["PASS"])
        self.assertEqual(stats["acceptance_fail"], expected_status_counts["FAIL"])
        self.assertEqual(stats["acceptance_need_more_params"], expected_status_counts["NEED_MORE_PARAMS"])
        self.assertEqual(stats["patch_files"], expected_patch_ready)
        self.assertEqual(stats["patch_applicable_count"], expected_patch_ready)
        self.assertEqual(stats["patch_strategy_counts"], dict(expected_strategy_counts))
        self.assertEqual(stats["dollar_substitution_count"], expected_security_count)
        self.assertEqual(stats["wrapper_collapse_recovered_count"], expected_wrapper_count)
        self.assertEqual(stats["blocked_sql_count"], expected_blocked_sql_count)
        self.assertEqual(stats["blocker_family_counts"], dict(expected_family_counts))
        self.assertEqual(stats["aggregation_shape_counts"], dict(expected_aggregation_shape_counts))
        self.assertEqual(stats["aggregation_constraint_counts"], dict(expected_aggregation_constraint_counts))
        self.assertEqual(stats["aggregation_safe_baseline_counts"], dict(expected_aggregation_safe_baseline_counts))
        self.assertEqual(stats["aggregation_ready_family_counts"], dict(expected_aggregation_ready_family_counts))
        self.assertEqual(stats["aggregation_ready_patch_count"], expected_aggregation_ready_patch_count)
        self.assertEqual(stats["dynamic_baseline_family_counts"], dict(expected_dynamic_baseline_family_counts))
        self.assertEqual(stats["dynamic_delivery_class_counts"], dict(expected_dynamic_delivery_class_counts))
        self.assertEqual(stats["dynamic_ready_baseline_family_counts"], dict(expected_dynamic_ready_baseline_family_counts))
        self.assertEqual(stats["dynamic_ready_patch_count"], expected_dynamic_ready_patch_count)
        self.assertEqual(stats["dynamic_safe_baseline_blocked_count"], expected_dynamic_safe_baseline_blocked_count)
        self.assertEqual(stats["dynamic_review_only_count"], expected_dynamic_review_only_count)
        self.assertEqual(len(acceptance_rows), len(scenarios))
        self.assertEqual(actual_family_counts, expected_family_counts)
        self.assertEqual(summary["roadmapStageCounts"]["NEXT"], 1)
        self.assertIn("demo.user.advanced.listDistinctUserStatuses#v11", summary["nextTargetSqlKeys"])
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


if __name__ == "__main__":
    unittest.main()
