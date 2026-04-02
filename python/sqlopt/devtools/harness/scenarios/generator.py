from __future__ import annotations

from typing import Any


FEATURE_PATTERNS = [
    (
        lambda f: "DOLLAR_SUBSTITUTION" in f,
        "PATCH_BLOCKED_SECURITY",
        None,
        "compare_disabled",
        "DOLLAR_SUBSTITUTION present - security blocker",
    ),
    (
        lambda f: f == [] or f == ["INCLUDE"],
        "PATCH_READY_STATEMENT",
        "EXACT_TEMPLATE_EDIT",
        "exact_match_improved",
        "simple statement can be edited",
    ),
    (
        lambda f: "WRAPPER" in str(f),
        "PATCH_READY_WRAPPER_COLLAPSE",
        "SAFE_WRAPPER_COLLAPSE",
        "exact_match_improved",
        "wrapper query can be collapsed",
    ),
    (
        lambda f: f == ["FOREACH"] or f == ["WHERE", "FOREACH"],
        "PATCH_READY_STATEMENT",
        "EXACT_TEMPLATE_EDIT",
        "exact_match_improved",
        "simple foreach can be edited",
    ),
    (
        lambda f: len(f) >= 2,
        "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
        None,
        "compare_disabled",
        "complex dynamic features - expected blocked",
    ),
    (
        lambda f: True,
        "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
        None,
        "compare_disabled",
        "generated scenario - conservative default",
    ),
]

DEFAULT_SCENARIO = {
    "scenarioClass": "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
    "targetPatchStrategy": None,
    "validateEvidenceMode": "compare_disabled",
    "purpose": "generated scenario - needs manual review",
}


def match_scenario_class(features: list[str]) -> dict[str, Any]:
    for check, scenario_class, strategy, validate_mode, purpose in FEATURE_PATTERNS:
        if check(features):
            return {
                "scenarioClass": scenario_class,
                "targetPatchStrategy": strategy,
                "validateEvidenceMode": validate_mode,
                "purpose": purpose,
            }
    return DEFAULT_SCENARIO.copy()


def generate_scenario(stmt: dict[str, Any]) -> dict[str, Any]:
    features = list(stmt["features"])
    risk_flags = list(stmt["riskFlags"])
    scenario = match_scenario_class(features)

    if stmt["statementType"] == "SELECT":
        validate_candidate = "SELECT * FROM users"
    elif stmt["statementType"] == "INSERT":
        validate_candidate = "INSERT INTO users (id, name) VALUES (1, 'test')"
    elif stmt["statementType"] == "UPDATE":
        validate_candidate = "UPDATE users SET name = 'test' WHERE id = 1"
    else:
        validate_candidate = "SELECT 1"

    if scenario["scenarioClass"].startswith("PATCH_READY"):
        target_validate_status = "PASS"
        target_semantic_gate = "PASS"
        target_patchability = "READY"
        target_primary_blocker = None
        target_blocker_family = "READY"
    elif scenario["scenarioClass"] == "PATCH_BLOCKED_SECURITY":
        target_validate_status = "NEED_MORE_PARAMS"
        target_semantic_gate = "BLOCKED"
        target_patchability = "BLOCKED"
        target_primary_blocker = "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"
        target_blocker_family = "SECURITY"
        scenario["targetPatchReasonCode"] = "PATCH_VALIDATION_BLOCKED_SECURITY"
    else:
        target_validate_status = "NEED_MORE_PARAMS"
        target_semantic_gate = "UNCERTAIN"
        target_patchability = "REVIEW"
        target_primary_blocker = "SEMANTIC_GATE_UNCERTAIN"
        target_blocker_family = "TEMPLATE_UNSUPPORTED"
        scenario["targetPatchReasonCode"] = "PATCH_CONFLICT_NO_CLEAR_WINNER"

    return {
        "sqlKey": stmt["sqlKey"],
        "statementType": stmt["statementType"],
        "mapperPath": stmt["xmlPath"],
        "domain": "test.complex",
        "scenarioClass": scenario["scenarioClass"],
        "purpose": f"generated: {scenario['purpose']}",
        "expectedScanFeatures": features,
        "expectedRiskFlags": risk_flags,
        "validateCandidateSql": validate_candidate,
        "validateEvidenceMode": scenario["validateEvidenceMode"],
        "targetValidateStatus": target_validate_status,
        "targetSemanticGate": target_semantic_gate,
        "targetPatchability": target_patchability,
        "targetPatchStrategy": scenario.get("targetPatchStrategy"),
        "targetPrimaryBlocker": target_primary_blocker,
        "targetPatchReasonCode": scenario.get("targetPatchReasonCode", "PATCH_CONFLICT_NO_CLEAR_WINNER"),
        "targetPatchMustContain": [],
        "targetPatchMustNotContain": [],
        "targetBlockerFamily": target_blocker_family,
        "roadmapStage": "EXTENSION",
        "roadmapTheme": "COMPLEX_DYNAMIC",
    }


def generate_extension_scenarios(units_by_key: dict[str, dict], *, existing_scenarios: list[dict]) -> list[dict]:
    existing_keys = {str(row["sqlKey"]) for row in existing_scenarios}
    generated: list[dict] = []
    for sql_key, unit in units_by_key.items():
        if sql_key in existing_keys or "complex" not in sql_key.lower():
            continue
        stmt = {
            "sqlKey": sql_key,
            "statementType": unit.get("statementType", "SELECT"),
            "statementId": unit.get("statementId", sql_key.split(".")[-1].split("#")[0]),
            "features": unit.get("dynamicFeatures", []),
            "riskFlags": unit.get("riskFlags", []),
            "xmlPath": unit.get("xmlPath", "src/main/resources/com/example/mapper/test/complex_harness_mapper.xml"),
        }
        generated.append(generate_scenario(stmt))
    return generated
