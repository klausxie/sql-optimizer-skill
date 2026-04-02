#!/usr/bin/env python3
"""Generate new EXTENSION fixture scenarios from scanned complex sample-project SQL."""

import sys

sys.path.insert(0, "python")

from sqlopt.devtools.harness.runtime import FIXTURE_SCENARIOS_PATH, scan_fixture_project
from sqlopt.devtools.harness.scenarios import generate_extension_scenarios, load_scenarios, save_scenarios


def main():
    print("Scanning fixture project...")

    _units, units_by_key, _fragments = scan_fixture_project()
    print(f"Found {len(units_by_key)} SQL units")

    complex_units = {k: v for k, v in units_by_key.items()
                     if 'complex' in k.lower()}
    print(f"Complex mapper statements: {len(complex_units)}")

    existing_scenarios = load_scenarios(FIXTURE_SCENARIOS_PATH)
    print(f"Existing scenarios (will be preserved): {len(existing_scenarios)}")

    new_scenarios = generate_extension_scenarios(complex_units, existing_scenarios=existing_scenarios)
    print(f"New scenarios to add: {len(new_scenarios)}")
    if not new_scenarios:
        print("No new scenarios to add.")
        return

    all_scenarios = existing_scenarios + new_scenarios
    save_scenarios(all_scenarios, FIXTURE_SCENARIOS_PATH)
    print(f"Updated {FIXTURE_SCENARIOS_PATH} with {len(all_scenarios)} total scenarios")

    classes = {}
    for s in all_scenarios:
        c = s.get('scenarioClass', 'UNKNOWN')
        classes[c] = classes.get(c, 0) + 1

    print("\nScenario class distribution:")
    for c, cnt in sorted(classes.items(), key=lambda x: -x[1]):
        print(f"  {c}: {cnt}")


if __name__ == '__main__':
    main()
