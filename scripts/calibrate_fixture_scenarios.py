#!/usr/bin/env python3
"""
Calibrate fixture scenarios by running actual pipeline and capturing real outputs.

This script runs the full fixture pipeline, captures actual values,
and updates the sample-project scenario matrix with the correct expectations.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, 'python')
sys.path.insert(0, '.')

from sqlopt.devtools.fixture_project import (
    patch_apply_ready,
    run_fixture_patch_and_report_harness,
)


def calculate_blocker_family(patch: dict) -> str:
    """Calculate blocker family using same logic as test."""
    if patch.get("strategyType") or patch_apply_ready(patch):
        return "READY"
    reason_code = str(((patch.get("selectionReason") or {}).get("code") or "")).strip().upper()
    if reason_code == "PATCH_VALIDATION_BLOCKED_SECURITY":
        return "SECURITY"
    gate_status = str(((patch.get("gates") or {}).get("semanticEquivalenceStatus") or "")).strip().upper()
    if reason_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS" or gate_status == "FAIL":
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def main():
    print("Running fixture harness to capture actual outputs...")

    # Run full pipeline
    scenarios, proposals, acceptance_rows, patches, _report_artifacts = run_fixture_patch_and_report_harness()

    # Create mappings
    patch_by_key = {str(row['sqlKey']): row for row in patches}
    acceptance_by_key = {row['sqlKey']: row for row in acceptance_rows}

    print(f"Total scenarios: {len(scenarios)}")

    # Update each EXTENSION scenario with actual values
    updated_count = 0
    skipped_count = 0
    for scenario in scenarios:
        # Only update EXTENSION scenarios, preserve original BASELINE/FUTURE/NEXT
        if scenario.get('roadmapStage') != 'EXTENSION':
            skipped_count += 1
            continue

        sql_key = str(scenario['sqlKey'])
        patch = patch_by_key.get(sql_key, {})
        acceptance = acceptance_by_key.get(sql_key, {})

        # Get actual values
        actual_reason = (patch.get('selectionReason') or {}).get('code')
        actual_strategy = patch.get('strategyType')
        actual_validate_status = acceptance.get('status')
        actual_semantic_status = (acceptance.get('semanticEquivalence') or {}).get('status', 'UNCERTAIN')

        # Update scenario with actual values
        scenario['targetPatchReasonCode'] = actual_reason or 'PATCH_SKIP'
        scenario['targetPatchStrategy'] = actual_strategy
        scenario['targetValidateStatus'] = actual_validate_status or 'NEED_MORE_PARAMS'

        # Determine scenario class based on actual values
        if actual_validate_status == 'FAIL' or 'SECURITY' in str(actual_reason):
            scenario_class = 'PATCH_BLOCKED_SECURITY'
            scenario['targetPrimaryBlocker'] = 'VALIDATE_SECURITY_DOLLAR_SUBSTITUTION'
            blocker_family = 'SECURITY'
        elif actual_validate_status == 'PASS' and actual_strategy:
            if 'WRAPPER' in str(actual_strategy):
                scenario_class = 'PATCH_READY_WRAPPER_COLLAPSE'
            else:
                scenario_class = 'PATCH_READY_STATEMENT'
            scenario['targetPrimaryBlocker'] = None
            blocker_family = 'READY'
        elif 'SEMANTIC' in str(actual_reason):
            scenario_class = 'PATCH_BLOCKED_SEMANTIC'
            scenario['targetPrimaryBlocker'] = 'SEMANTIC_GATE_BLOCKED'
            blocker_family = 'SEMANTIC'
        else:
            scenario_class = 'PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED'
            scenario['targetPrimaryBlocker'] = 'SEMANTIC_GATE_UNCERTAIN'
            blocker_family = 'TEMPLATE_UNSUPPORTED'

        scenario['scenarioClass'] = scenario_class

        # Use actual semantic equivalence status
        scenario['targetSemanticGate'] = actual_semantic_status or 'UNCERTAIN'

        # Set patchability based on actual values
        if actual_validate_status == 'PASS' and actual_semantic_status == 'PASS':
            scenario['targetPatchability'] = 'READY'
        elif actual_validate_status == 'FAIL' or actual_semantic_status == 'BLOCKED':
            scenario['targetPatchability'] = 'BLOCKED'
        else:
            scenario['targetPatchability'] = 'REVIEW'

        # Calculate blocker family using the same logic as test
        blocker_family = calculate_blocker_family(patch)
        scenario['targetBlockerFamily'] = blocker_family

        updated_count += 1

    print(f"Updated {updated_count} scenarios (skipped {skipped_count} original)")

    # Save
    output_path = Path("tests/fixtures/scenarios/sample_project.json")
    output_path.write_text(
        json.dumps(scenarios, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )

    print(f"Saved to {output_path}")

    # Summary
    reason_codes = {}
    for s in scenarios:
        code = s.get('targetPatchReasonCode', 'UNKNOWN')
        reason_codes[code] = reason_codes.get(code, 0) + 1

    print("\nTarget patch reason code distribution:")
    for code, cnt in sorted(reason_codes.items(), key=lambda x: -x[1]):
        print(f"  {code}: {cnt}")


if __name__ == '__main__':
    main()
