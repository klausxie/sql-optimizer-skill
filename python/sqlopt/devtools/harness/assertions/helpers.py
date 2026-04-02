from __future__ import annotations

from ....patch_families.registry import lookup_patch_family_spec
from ....stages.report_stats import blocker_family_for_patch_row

_DYNAMIC_BLOCKED_DELIVERY_CLASSES = {"SAFE_BASELINE_BLOCKED", "SAFE_BASELINE_NO_DIFF"}


def registered_patch_family_spec(family: str | None) -> object | None:
    normalized_family = str(family or "").strip()
    if not normalized_family:
        return None
    return lookup_patch_family_spec(normalized_family)


def dynamic_blocked_neighbor_families(scenarios: list[dict]) -> set[str]:
    blocked_families: set[str] = set()
    for row in scenarios:
        family = str(row.get("targetDynamicBaselineFamily") or "").strip()
        delivery_class = str(row.get("targetDynamicDeliveryClass") or "").strip().upper()
        if delivery_class not in _DYNAMIC_BLOCKED_DELIVERY_CLASSES:
            continue
        spec = registered_patch_family_spec(family)
        if spec is not None:
            blocked_families.add(str(spec.family))
    return blocked_families


def fixture_dynamic_registered_families(scenarios: list[dict]) -> set[str]:
    registered_families: set[str] = set()
    for row in scenarios:
        spec = registered_patch_family_spec(row.get("targetDynamicBaselineFamily"))
        if spec is not None:
            registered_families.add(str(spec.family))
    return registered_families


def fixture_registered_families(scenarios: list[dict]) -> set[str]:
    registered_families = fixture_dynamic_registered_families(scenarios)
    for row in scenarios:
        spec = registered_patch_family_spec(row.get("targetRegisteredFamily"))
        if spec is not None:
            registered_families.add(str(spec.family))
    return registered_families


def fixture_registered_blocked_neighbor_families(scenarios: list[dict]) -> set[str]:
    blocked_families = set(dynamic_blocked_neighbor_families(scenarios))
    for row in scenarios:
        if row.get("targetPatchStrategy"):
            continue
        scenario_class = str(row.get("scenarioClass") or "").strip().upper()
        patchability = str(row.get("targetPatchability") or "").strip().upper()
        if scenario_class not in {"PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED", "PATCH_BLOCKED_SEMANTIC"} and patchability not in {
            "REVIEW",
            "BLOCKED",
        }:
            continue
        spec = registered_patch_family_spec(row.get("targetRegisteredFamily"))
        if spec is not None:
            blocked_families.add(str(spec.family))
    return blocked_families


def patch_apply_ready(patch: dict) -> bool:
    delivery_stage = str(patch.get("deliveryStage") or "").strip().upper()
    if delivery_stage:
        return delivery_stage == "APPLY_READY"
    return patch.get("applicable") is True


def patch_meets_registered_fixture_obligations(patch: dict, scenario: dict) -> bool:
    target_registered_family = str(scenario.get("targetRegisteredFamily") or "").strip()
    target_dynamic_family = str(scenario.get("targetDynamicBaselineFamily") or "").strip()
    tracked_family = target_registered_family or target_dynamic_family
    spec = registered_patch_family_spec(tracked_family)
    if spec is None:
        return True

    patch_target_family = str(patch.get("patchFamily") or "").strip()
    applicable = patch_apply_ready(patch)
    dynamic_delivery_class = str(scenario.get("targetDynamicDeliveryClass") or "").strip().upper()

    if target_registered_family and applicable and patch_target_family != str(spec.family):
        return False
    if dynamic_delivery_class == "READY_DYNAMIC_PATCH":
        if not applicable or patch_target_family != str(spec.family):
            return False
    if not applicable:
        return True

    if spec.fixture_obligations.replay_assertions_required and spec.verification.require_replay_match:
        if ((patch.get("replayEvidence") or {}).get("matchesTarget")) is not True:
            return False

    if spec.fixture_obligations.verification_assertions_required:
        syntax_evidence = patch.get("syntaxEvidence") or {}
        if spec.verification.require_xml_parse and syntax_evidence.get("xmlParseOk") is not True:
            return False
        if spec.verification.require_render_ok and syntax_evidence.get("renderOk") is not True:
            return False
        if spec.verification.require_sql_parse and syntax_evidence.get("sqlParseOk") is not True:
            return False

    return True


def semantic_gate_bucket(result: dict) -> str:
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code.startswith("VALIDATE_SECURITY_"):
        return "BLOCKED"
    gate = result.get("semanticEquivalence") or {}
    return str(gate.get("status") or "UNCERTAIN").upper()


def patchability_bucket(result: dict) -> str:
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code.startswith("VALIDATE_SECURITY_"):
        return "BLOCKED"
    patchability = result.get("patchability") or {}
    if bool(patchability.get("eligible")):
        return "READY"
    gate = semantic_gate_bucket(result)
    if gate == "FAIL" or str(result.get("status") or "").upper() == "FAIL":
        return "BLOCKED"
    return "REVIEW"


def primary_blocker(result: dict) -> str | None:
    patchability = result.get("patchability") or {}
    if bool(patchability.get("eligible")):
        return None
    code = str(patchability.get("blockingReason") or "").strip()
    if code:
        return code
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code:
        return feedback_code
    gate = result.get("semanticEquivalence") or {}
    reasons = [str(x) for x in (gate.get("reasons") or []) if str(x).strip()]
    return reasons[0] if reasons else None


def validate_blocker_family(result: dict) -> str:
    if bool((result.get("patchability") or {}).get("eligible")):
        return "READY"
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip().upper()
    if feedback_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "SECURITY"
    gate_status = str(((result.get("semanticEquivalence") or {}).get("status") or "")).strip().upper()
    if gate_status == "FAIL" or str(result.get("status") or "").upper() == "FAIL":
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def patch_blocker_family(patch: dict) -> str:
    return blocker_family_for_patch_row(patch)
