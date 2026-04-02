#!/usr/bin/env python3
"""Calibrate EXTENSION fixture scenarios from the current patch/report harness outputs."""

import sys

sys.path.insert(0, 'python')
sys.path.insert(0, '.')

from sqlopt.devtools.harness.runtime import FIXTURE_SCENARIOS_PATH, run_fixture_patch_and_report_harness
from sqlopt.devtools.harness.scenarios import calibrate_extension_scenarios, save_scenarios


def main():
    print("Running fixture harness to capture actual outputs...")

    scenarios, _proposals, acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()
    scenarios = calibrate_extension_scenarios(
        scenarios,
        acceptance_rows=acceptance_rows,
        patches=patches,
    )
    print(f"Total scenarios: {len(scenarios)}")

    updated_count = sum(1 for scenario in scenarios if scenario.get('roadmapStage') == 'EXTENSION')
    skipped_count = len(scenarios) - updated_count
    print(f"Updated {updated_count} scenarios (skipped {skipped_count} original)")

    output_path = save_scenarios(scenarios, FIXTURE_SCENARIOS_PATH)
    print(f"Saved to {output_path}")

    reason_codes = {}
    for s in scenarios:
        code = s.get('targetPatchReasonCode', 'UNKNOWN')
        reason_codes[code] = reason_codes.get(code, 0) + 1

    print("\nTarget patch reason code distribution:")
    for code, cnt in sorted(reason_codes.items(), key=lambda x: -x[1]):
        print(f"  {code}: {cnt}")


if __name__ == '__main__':
    main()
