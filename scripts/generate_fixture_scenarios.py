#!/usr/bin/env python3
"""
Generate fixture scenarios for complex SQL statements in complex_harness_mapper.xml.

This script scans the complex_harness_mapper.xml file, extracts all SQL statements,
and generates fixture scenarios with reasonable default expectations.
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any

ROOT = Path("tests/fixtures/project")
XML_PATH = ROOT / "src/main/resources/com/example/mapper/test/complex_harness_mapper.xml"
SCENARIOS_PATH = ROOT / "fixture_scenarios.json"

# Feature patterns to scenario class mapping
# More conservative - most complex SQL won't generate patches
FEATURE_PATTERNS = [
    # (features_check, scenario_class, strategy, validate_mode, purpose)
    # DOLLAR_SUBSTITUTION - security blocked
    (lambda f: 'DOLLAR_SUBSTITUTION' in f,
     'PATCH_BLOCKED_SECURITY', None, 'compare_disabled',
     'DOLLAR_SUBSTITUTION present - security blocker'),
    # Empty or very simple - could be READY
    (lambda f: f == [] or f == ['INCLUDE'],
     'PATCH_READY_STATEMENT', 'EXACT_TEMPLATE_EDIT', 'exact_match_improved',
     'simple statement can be edited'),
    # Wrapper - could be READY
    (lambda f: 'WRAPPER' in str(f),
     'PATCH_READY_WRAPPER_COLLAPSE', 'SAFE_WRAPPER_COLLAPSE', 'exact_match_improved',
     'wrapper query can be collapsed'),
    # Simple FOREACH only - could work
    (lambda f: f == ['FOREACH'] or f == ['WHERE', 'FOREACH'],
     'PATCH_READY_STATEMENT', 'EXACT_TEMPLATE_EDIT', 'exact_match_improved',
     'simple foreach can be edited'),
    # Most complex dynamic SQL - BLOCKED
    (lambda f: len(f) >= 2,
     'PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED', None, 'compare_disabled',
     'complex dynamic features - expected blocked'),
    # Default - conservative
    (lambda f: True,
     'PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED', None, 'compare_disabled',
     'generated scenario - conservative default'),
]

# Default for unmatched
DEFAULT_SCENARIO = {
    'scenarioClass': 'PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED',
    'targetPatchStrategy': None,
    'validateEvidenceMode': 'compare_disabled',
    'purpose': 'generated scenario - needs manual review',
}


def parse_xml_statements(xml_path: Path) -> list[dict[str, Any]]:
    """Parse XML and extract all SQL statements with their features."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    statements = []

    # Parse select, insert, update, delete statements
    for stmt_type in ['select', 'insert', 'update', 'delete']:
        for elem in root.findall(f".//{stmt_type}"):
            stmt_id = elem.get('id')
            if not stmt_id:
                continue

            # Get namespace from parent
            namespace = elem.get('namespace', 'demo.test.complex')
            sql_key = f"{namespace}.{stmt_id}#v1"

            # Get statement type
            statement_type = stmt_type.upper()

            # Check for dynamic features
            features = []
            risk_flags = []

            # Check inner elements for dynamic tags
            xml_str = ET.tostring(elem, encoding='unicode')

            if '<include ' in xml_str:
                features.append('INCLUDE')
            if '<where' in xml_str:
                features.append('WHERE')
            if '<if ' in xml_str:
                features.append('IF')
            if '<foreach ' in xml_str:
                features.append('FOREACH')
            if '<choose' in xml_str:
                features.append('CHOOSE')
            if '<trim' in xml_str:
                features.append('TRIM')
            if '<set' in xml_str:
                features.append('SET')
            if '<bind ' in xml_str:
                features.append('BIND')
            if '${' in xml_str:  # Dollar substitution
                risk_flags.append('DOLLAR_SUBSTITUTION')
                features.append('DOLLAR_SUBSTITUTION')

            statements.append({
                'sqlKey': sql_key,
                'statementType': statement_type,
                'statementId': stmt_id,
                'features': features,
                'riskFlags': risk_flags,
                'xmlPath': str(xml_path.relative_to(ROOT)),
            })

    return statements


def match_scenario_class(features: list[str]) -> dict[str, Any]:
    """Match features to scenario class and defaults."""
    for check, scenario_class, strategy, validate_mode, purpose in FEATURE_PATTERNS:
        if check(features):
            return {
                'scenarioClass': scenario_class,
                'targetPatchStrategy': strategy,
                'validateEvidenceMode': validate_mode,
                'purpose': purpose,
            }
    return DEFAULT_SCENARIO.copy()


def generate_scenario(stmt: dict[str, Any]) -> dict[str, Any]:
    """Generate a fixture scenario for a statement."""
    features = stmt['features']
    risk_flags = stmt['riskFlags']

    # Get base scenario from feature matching
    scenario = match_scenario_class(features)

    # Build validate candidate SQL (simplified)
    if stmt['statementType'] == 'SELECT':
        validate_candidate = "SELECT * FROM users"
    elif stmt['statementType'] == 'INSERT':
        validate_candidate = "INSERT INTO users (id, name) VALUES (1, 'test')"
    elif stmt['statementType'] == 'UPDATE':
        validate_candidate = "UPDATE users SET name = 'test' WHERE id = 1"
    else:
        validate_candidate = "SELECT 1"

    # Determine expected values based on scenario class
    if scenario['scenarioClass'].startswith('PATCH_READY'):
        target_validate_status = 'PASS'
        target_semantic_gate = 'PASS'
        target_patchability = 'READY'
        target_primary_blocker = None
        target_blocker_family = 'READY'
    elif scenario['scenarioClass'] == 'PATCH_BLOCKED_SECURITY':
        target_validate_status = 'NEED_MORE_PARAMS'
        target_semantic_gate = 'BLOCKED'
        target_patchability = 'BLOCKED'
        target_primary_blocker = 'VALIDATE_SECURITY_DOLLAR_SUBSTITUTION'
        target_blocker_family = 'SECURITY'
        scenario['targetPatchReasonCode'] = 'PATCH_VALIDATION_BLOCKED_SECURITY'
    else:
        # BLOCKED_TEMPLATE_OR_UNSUPPORTED
        target_validate_status = 'NEED_MORE_PARAMS'
        target_semantic_gate = 'UNCERTAIN'
        target_patchability = 'REVIEW'
        target_primary_blocker = 'SEMANTIC_GATE_UNCERTAIN'
        target_blocker_family = 'TEMPLATE_UNSUPPORTED'
        scenario['targetPatchReasonCode'] = 'PATCH_CONFLICT_NO_CLEAR_WINNER'

    # Build the scenario
    return {
        'sqlKey': stmt['sqlKey'],
        'statementType': stmt['statementType'],
        'mapperPath': stmt['xmlPath'],
        'domain': 'test.complex',
        'scenarioClass': scenario['scenarioClass'],
        'purpose': f"generated: {scenario['purpose']}",
        'expectedScanFeatures': features,
        'expectedRiskFlags': risk_flags,
        'validateCandidateSql': validate_candidate,
        'validateEvidenceMode': scenario['validateEvidenceMode'],
        'targetValidateStatus': target_validate_status,
        'targetSemanticGate': target_semantic_gate,
        'targetPatchability': target_patchability,
        'targetPatchStrategy': scenario.get('targetPatchStrategy'),
        'targetPrimaryBlocker': target_primary_blocker,
        'targetPatchReasonCode': scenario.get('targetPatchReasonCode', 'PATCH_CONFLICT_NO_CLEAR_WINNER'),
        'targetPatchMustContain': [],
        'targetPatchMustNotContain': [],
        'targetBlockerFamily': target_blocker_family,
        'roadmapStage': 'EXTENSION',
        'roadmapTheme': 'COMPLEX_DYNAMIC',
    }


def main():
    """Main function."""
    print("Scanning fixture project...")

    # First, scan to get actual SQL units
    import sys
    sys.path.insert(0, 'tests')
    from fixture_project_harness_support import scan_fixture_project

    units, units_by_key, fragments = scan_fixture_project()
    print(f"Found {len(units_by_key)} SQL units")

    # Filter to only complex mapper statements
    complex_units = {k: v for k, v in units_by_key.items()
                     if 'complex' in k.lower()}

    print(f"Complex mapper statements: {len(complex_units)}")

    # Load existing scenarios - PRESERVE them!
    existing_scenarios = json.loads(SCENARIOS_PATH.read_text(encoding='utf-8'))
    existing_keys = {s['sqlKey'] for s in existing_scenarios}
    print(f"Existing scenarios (will be preserved): {len(existing_scenarios)}")

    # Generate scenarios for new statements only
    new_scenarios = []
    for sql_key, unit in complex_units.items():
        if sql_key in existing_keys:
            continue  # Skip if already exists

        stmt = {
            'sqlKey': sql_key,
            'statementType': unit.get('statementType', 'SELECT'),
            'statementId': unit.get('statementId', sql_key.split('.')[-1].split('#')[0]),
            'features': unit.get('dynamicFeatures', []),
            'riskFlags': unit.get('riskFlags', []),
            'xmlPath': unit.get('xmlPath', 'src/main/resources/com/example/mapper/test/complex_harness_mapper.xml'),
        }
        scenario = generate_scenario(stmt)
        # Mark as EXTENSION for tracking
        scenario['roadmapStage'] = 'EXTENSION'
        new_scenarios.append(scenario)

    print(f"New scenarios to add: {len(new_scenarios)}")

    if not new_scenarios:
        print("No new scenarios to add.")
        return

    # Merge: keep original + add new
    all_scenarios = existing_scenarios + new_scenarios
    SCENARIOS_PATH.write_text(
        json.dumps(all_scenarios, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )

    print(f"Updated fixture_scenarios.json with {len(all_scenarios)} total scenarios")

    if not new_scenarios:
        print("No new scenarios to add.")
        return

    # Merge and save
    all_scenarios = existing_scenarios + new_scenarios
    SCENARIOS_PATH.write_text(
        json.dumps(all_scenarios, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8'
    )

    print(f"Updated fixture_scenarios.json with {len(all_scenarios)} total scenarios")

    # Summary
    classes = {}
    for s in all_scenarios:
        c = s.get('scenarioClass', 'UNKNOWN')
        classes[c] = classes.get(c, 0) + 1

    print("\nScenario class distribution:")
    for c, cnt in sorted(classes.items(), key=lambda x: -x[1]):
        print(f"  {c}: {cnt}")


if __name__ == '__main__':
    main()