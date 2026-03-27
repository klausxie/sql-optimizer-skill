from __future__ import annotations

from typing import Any

from .patch_build import PatchBuildResult
from .patch_select import PatchSelectionContext

BUILD_FAILURE_REASON_CODES = {
    "PATCH_LOCATOR_AMBIGUOUS",
    "PATCH_NO_EFFECTIVE_CHANGE",
    "PATCH_TEMPLATE_MATERIALIZATION_MISSING",
    "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED",
    "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
    "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE",
    "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED",
    "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED",
    "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED",
    "PATCH_CONFLICT_NO_CLEAR_WINNER",
    "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
    "PATCH_SEMANTIC_CONFIDENCE_LOW",
    "PATCH_VALIDATION_BLOCKED_SECURITY",
}
PROOF_FAILURE_REASON_CODES = {
    "PATCH_TARGET_DRIFT",
    "PATCH_ARTIFACT_INVALID",
    "PATCH_XML_PARSE_FAILED",
    "PATCH_SQL_PARSE_FAILED",
    "PATCH_TARGET_CONTRACT_MISSING",
    "PATCH_FAMILY_SPEC_MISSING",
}

LLM_ASSIST_REASON_CODES = {
    "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
    "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE",
    "PATCH_NOT_APPLICABLE",
    "PATCH_VALIDATION_BLOCKED_SECURITY",
    "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
    "PATCH_SEMANTIC_CONFIDENCE_LOW",
}


def build_patch_repair_hints(reason_code: str, apply_check_error: str | None, sql_unit: dict[str, Any]) -> list[dict[str, Any]]:
    xml_path = str(sql_unit.get("xmlPath") or "").strip()
    if reason_code == "PATCH_NOT_APPLICABLE":
        return [
            {
                "hintId": "review-target-drift",
                "title": "Check target mapper drift",
                "detail": "the generated patch no longer applies cleanly to the current mapper file",
                "actionType": "GIT_CONFLICT",
                "command": f"git diff -- {xml_path}" if xml_path else None,
            }
        ]
    if reason_code == "PATCH_LOCATOR_AMBIGUOUS":
        return [
            {
                "hintId": "stabilize-locator",
                "title": "Stabilize statement locator",
                "detail": "add a stable statementId or preserve enough structure for deterministic targeting",
                "actionType": "MAPPER_REFACTOR",
                "command": None,
            }
        ]
    if reason_code == "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE":
        return [
            {
                "hintId": "expand-include",
                "title": "Refactor include fragment path",
                "detail": "expand or isolate included fragments before relying on automatic patch generation",
                "actionType": "MAPPER_REFACTOR",
                "command": None,
            }
        ]
    if reason_code == "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE":
        return [
            {
                "hintId": "use-template-rewrite",
                "title": "Prefer template-aware rewrite",
                "detail": "this dynamic mapper shape requires template-aware rewriting instead of flattened SQL replacement",
                "actionType": "SQL_REWRITE",
                "command": None,
            }
        ]
    if reason_code == "PATCH_CONFLICT_NO_CLEAR_WINNER":
        return [
            {
                "hintId": "collapse-candidates",
                "title": "Resolve competing winners",
                "detail": "reduce multiple PASS variants before generating a patch",
                "actionType": "MANUAL_PATCH",
                "command": None,
            }
        ]
    if reason_code == "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED":
        return [
            {
                "hintId": "review-template-duplicate-clause",
                "title": "Review duplicate template clause",
                "detail": "template rewrite contains duplicated major SQL clause and needs manual review",
                "actionType": "MANUAL_PATCH",
                "command": None,
            }
        ]
    if reason_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS":
        return [
            {
                "hintId": "review-semantic-gate",
                "title": "Review semantic equivalence gate",
                "detail": "semantic gate is not PASS; verify projection/predicate/order/pagination consistency before patching",
                "actionType": "MANUAL_REVIEW",
                "command": None,
            }
        ]
    if reason_code == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        return [
            {
                "hintId": "collect-semantic-evidence",
                "title": "Collect stronger semantic evidence",
                "detail": "semantic gate passed structurally but confidence is low; run stronger DB evidence checks before patching",
                "actionType": "MANUAL_REVIEW",
                "command": None,
            }
        ]
    if reason_code == "PATCH_VALIDATION_BLOCKED_SECURITY":
        return [
            {
                "hintId": "remove-dollar-substitution",
                "title": "Replace unsafe ${} interpolation",
                "detail": "convert ${} dynamic fragments to #{} binding or whitelist-driven branches before retrying patch generation",
                "actionType": "SQL_REWRITE",
                "command": None,
            },
            {
                "hintId": "restrict-dynamic-order-by",
                "title": "Whitelist dynamic ORDER BY keys",
                "detail": "map dynamic sort inputs to an explicit allow-list to avoid SQL injection patterns",
                "actionType": "MANUAL_REVIEW",
                "command": None,
            },
        ]
    if apply_check_error:
        return [
            {
                "hintId": "review-apply-error",
                "title": "Inspect apply-check failure",
                "detail": apply_check_error,
                "actionType": "GIT_CONFLICT",
                "command": f"git diff -- {xml_path}" if xml_path else None,
            }
        ]
    return []


def attach_patch_diagnostics(
    patch: dict[str, Any],
    sql_unit: dict[str, Any],
    selection: PatchSelectionContext,
    build: PatchBuildResult,
) -> dict[str, Any]:
    selection_reason = dict(patch.get("selectionReason") or {})
    reason_code = str(selection_reason.get("code") or "").strip()
    apply_check_error = patch.get("applyCheckError")
    template_ops = [row for row in build.template_rewrite_ops if isinstance(row, dict)]
    rewrite_materialization = dict(build.rewrite_materialization or {})
    replay_verified = rewrite_materialization.get("replayVerified")
    semantic_gate = dict(selection.semantic_equivalence or {})
    semantic_gate_status = str(selection.semantic_gate_status or semantic_gate.get("status") or "PASS").strip().upper()
    semantic_gate_confidence = str(selection.semantic_gate_confidence or semantic_gate.get("confidence") or "LOW").strip().upper()
    semantic_evidence_level = str(semantic_gate.get("evidenceLevel") or "STRUCTURE").strip().upper()
    selected_patch_strategy = dict(build.selected_patch_strategy or {})
    patch_family = str(build.family or "").strip() or None
    dynamic_template = dict(selection.dynamic_template or {})
    locator_stable = bool(((sql_unit.get("locators") or {}).get("statementId")))
    template_safe_path = bool(template_ops) and replay_verified is True
    structural_blockers = [reason_code] if reason_code and patch.get("applicable") is not True else []

    review_only_codes = {
        "PATCH_NOT_APPLICABLE",
        "PATCH_TARGET_DRIFT",
        "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
        "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE",
        "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED",
        "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED",
        "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED",
        "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED",
    }
    if patch.get("deliveryStage") == "PROOF_FAILED" or reason_code in PROOF_FAILURE_REASON_CODES:
        delivery_outcome = {
            "tier": "REVIEW_ONLY",
            "reasonCodes": [reason_code] if reason_code else [],
            "summary": "patch passed apply checks but proof verification failed",
        }
    elif patch.get("applicable") is True:
        delivery_outcome = {
            "tier": "AUTO_PATCH",
            "reasonCodes": [reason_code or "PATCH_SELECTED_SINGLE_PASS"],
            "summary": "patch is ready to apply",
        }
    elif reason_code in review_only_codes:
        delivery_outcome = {
            "tier": "REVIEW_ONLY",
            "reasonCodes": [reason_code],
            "summary": "patch direction is retained for review, but automatic delivery is blocked",
        }
    elif reason_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS":
        delivery_outcome = {
            "tier": "BLOCKED",
            "reasonCodes": [reason_code],
            "summary": "patch generation was blocked because semantic equivalence gate is not PASS",
        }
    elif reason_code == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        delivery_outcome = {
            "tier": "BLOCKED",
            "reasonCodes": [reason_code],
            "summary": "patch generation was blocked because semantic confidence is LOW",
        }
    elif reason_code == "PATCH_VALIDATION_BLOCKED_SECURITY":
        delivery_outcome = {
            "tier": "PATCHABLE_WITH_REWRITE",
            "reasonCodes": [reason_code, "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"],
            "summary": "patch generation was blocked by unsafe ${} substitution, but mapper rewrite can unblock delivery",
        }
    else:
        delivery_outcome = {
            "tier": "BLOCKED",
            "reasonCodes": [reason_code] if reason_code else [],
            "summary": "automatic patch generation is blocked by current mapper or candidate shape",
        }

    patch["deliveryOutcome"] = delivery_outcome
    if patch_family is not None:
        patch["patchFamily"] = patch_family
    patch["artifactKind"] = str(patch.get("artifactKind") or build.artifact_kind)
    if reason_code in PROOF_FAILURE_REASON_CODES:
        patch["deliveryStage"] = "PROOF_FAILED"
        patch["failureClass"] = "PROOF_FAILURE"
    elif patch.get("applicable") is False:
        patch["deliveryStage"] = "APPLICABILITY_FAILED"
        patch["failureClass"] = "APPLICABILITY_FAILURE"
    elif reason_code in BUILD_FAILURE_REASON_CODES:
        patch["deliveryStage"] = "BUILD_FAILED"
        patch["failureClass"] = "BUILD_FAILURE"
    elif patch.get("applicable") is True:
        patch["deliveryStage"] = "APPLY_READY"
        patch["failureClass"] = None
    patch["repairHints"] = build_patch_repair_hints(reason_code, apply_check_error, sql_unit)
    patch["patchability"] = {
        "applyCheckPassed": True if patch.get("applicable") is True else (False if patch.get("applicable") is False else None),
        "templateSafePath": template_safe_path,
        "locatorStable": locator_stable,
        "structuralBlockers": structural_blockers,
    }
    patch["gates"] = {
        "semanticEquivalenceStatus": semantic_gate_status,
        "semanticEquivalenceBlocking": reason_code in {"PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS", "PATCH_SEMANTIC_CONFIDENCE_LOW"},
        "semanticConfidence": semantic_gate_confidence,
        "semanticEvidenceLevel": semantic_evidence_level,
    }
    if selected_patch_strategy:
        patch["strategyType"] = selected_patch_strategy.get("strategyType")
        patch["fallbackApplied"] = bool(selected_patch_strategy.get("fallbackFrom"))
    if dynamic_template:
        patch["dynamicTemplateBlockingReason"] = dynamic_template.get("blockingReason")
        if str(selected_patch_strategy.get("strategyType") or "").startswith("DYNAMIC_"):
            patch["dynamicTemplateStrategy"] = selected_patch_strategy.get("strategyType")
    return patch


def should_call_llm_assist(patch: dict[str, Any]) -> bool:
    selection_reason = patch.get("selectionReason") or {}
    reason_code = str(selection_reason.get("code") or "")
    return patch.get("applicable") is not True or reason_code in LLM_ASSIST_REASON_CODES
