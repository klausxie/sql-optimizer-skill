from __future__ import annotations

from ..assertions.helpers import patch_apply_ready


def calculate_blocker_family(patch: dict) -> str:
    if patch.get("strategyType") or patch_apply_ready(patch):
        return "READY"
    reason_code = str(((patch.get("selectionReason") or {}).get("code") or "")).strip().upper()
    if reason_code == "PATCH_VALIDATION_BLOCKED_SECURITY":
        return "SECURITY"
    gate_status = str(((patch.get("gates") or {}).get("semanticEquivalenceStatus") or "")).strip().upper()
    if reason_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS" or gate_status == "FAIL":
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def calibrate_extension_scenarios(
    scenarios: list[dict],
    *,
    acceptance_rows: list[dict],
    patches: list[dict],
) -> list[dict]:
    calibrated = [dict(row) for row in scenarios]
    patch_by_key = {str(row["sqlKey"]): row for row in patches}
    acceptance_by_key = {str(row["sqlKey"]): row for row in acceptance_rows}

    for scenario in calibrated:
        if scenario.get("roadmapStage") != "EXTENSION":
            continue

        sql_key = str(scenario["sqlKey"])
        patch = patch_by_key.get(sql_key, {})
        acceptance = acceptance_by_key.get(sql_key, {})

        actual_reason = (patch.get("selectionReason") or {}).get("code")
        actual_strategy = patch.get("strategyType")
        actual_validate_status = acceptance.get("status")
        actual_semantic_status = (acceptance.get("semanticEquivalence") or {}).get("status", "UNCERTAIN")

        scenario["targetPatchReasonCode"] = actual_reason or "PATCH_SKIP"
        scenario["targetPatchStrategy"] = actual_strategy
        scenario["targetValidateStatus"] = actual_validate_status or "NEED_MORE_PARAMS"

        if actual_validate_status == "FAIL" or "SECURITY" in str(actual_reason):
            scenario["scenarioClass"] = "PATCH_BLOCKED_SECURITY"
            scenario["targetPrimaryBlocker"] = "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"
        elif actual_validate_status == "PASS" and actual_strategy:
            scenario["scenarioClass"] = (
                "PATCH_READY_WRAPPER_COLLAPSE" if "WRAPPER" in str(actual_strategy) else "PATCH_READY_STATEMENT"
            )
            scenario["targetPrimaryBlocker"] = None
        elif "SEMANTIC" in str(actual_reason):
            scenario["scenarioClass"] = "PATCH_BLOCKED_SEMANTIC"
            scenario["targetPrimaryBlocker"] = "SEMANTIC_GATE_BLOCKED"
        else:
            scenario["scenarioClass"] = "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED"
            scenario["targetPrimaryBlocker"] = "SEMANTIC_GATE_UNCERTAIN"

        scenario["targetSemanticGate"] = actual_semantic_status or "UNCERTAIN"

        if actual_validate_status == "PASS" and actual_semantic_status == "PASS":
            scenario["targetPatchability"] = "READY"
        elif actual_validate_status == "FAIL" or actual_semantic_status == "BLOCKED":
            scenario["targetPatchability"] = "BLOCKED"
        else:
            scenario["targetPatchability"] = "REVIEW"

        scenario["targetBlockerFamily"] = calculate_blocker_family(patch)

    return calibrated
