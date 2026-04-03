from __future__ import annotations

import unittest

from sqlopt.devtools.harness.assertions import (
    assert_auto_patches_frozen_and_verified,
    assert_fixture_scenario_summary,
    assert_patch_matrix_matches_scenarios,
    assert_registered_fixture_patch_obligations,
)
from sqlopt.devtools.harness.runtime import (
    run_fixture_patch_and_report_harness,
)
from sqlopt.devtools.harness.scenarios import (
    summarize_fixture_scenarios,
)


class HarnessPatchAssertionsTest(unittest.TestCase):
    def test_patch_assertions_accept_current_fixture_patch_and_report_harness(self) -> None:
        scenarios, _proposals, _acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
        assert_registered_fixture_patch_obligations(scenarios, patches)
        assert_auto_patches_frozen_and_verified(patches)
        assert_patch_matrix_matches_scenarios(scenarios, patches)

    def test_fixture_summary_assertion_accepts_current_matrix_baseline(self) -> None:
        scenarios, _proposals, _acceptance_rows, _patches, _report_artifacts = run_fixture_patch_and_report_harness()
        summary = summarize_fixture_scenarios(scenarios)
        assert_fixture_scenario_summary(
            summary,
            next_count=1,
            next_target_sql_key="demo.user.advanced.listDistinctUserStatuses",
            roadmap_theme_counts={"CTE_ENABLEMENT": 1},
        )


if __name__ == "__main__":
    unittest.main()
