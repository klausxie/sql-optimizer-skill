from __future__ import annotations

from typing import Any

from .proposal_models import LLM_CANDIDATES_KEY


def _patch_apply_ready(patch_row: dict[str, Any]) -> bool:
    delivery_stage = str(patch_row.get("deliveryStage") or "").strip().upper()
    if delivery_stage:
        return delivery_stage == "APPLY_READY"
    return patch_row.get("applicable") is True


def blocker_family_for_outcome(
    *,
    delivery_status: str,
    blocker_primary_code: str | None,
    semantic_gate_status: str | None,
) -> str:
    normalized_delivery = str(delivery_status or "").strip().upper()
    normalized_code = str(blocker_primary_code or "").strip().upper()
    normalized_gate = str(semantic_gate_status or "").strip().upper()
    if normalized_delivery == "READY_TO_APPLY":
        return "READY"
    if normalized_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "SECURITY"
    if normalized_gate == "FAIL" or normalized_code in {
        "SEMANTIC_GATE_FAIL",
        "VALIDATE_EQUIVALENCE_MISMATCH",
        "VALIDATE_SEMANTIC_ERROR",
        "VALIDATE_SEMANTIC_CONFIDENCE_LOW",
        "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        "PATCH_SEMANTIC_CONFIDENCE_LOW",
    }:
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def blocker_family_for_patch_row(
    patch_row: dict[str, Any] | None,
    *,
    semantic_gate_status: str | None = None,
) -> str:
    patch_payload = dict(patch_row or {})
    strategy_type = str(patch_payload.get("strategyType") or "").strip().upper()
    selection_code = str(((patch_payload.get("selectionReason") or {}).get("code") or "")).strip().upper()
    gate_status = str(
        ((patch_payload.get("gates") or {}).get("semanticEquivalenceStatus") or semantic_gate_status or "")
    ).strip().upper()
    if strategy_type or _patch_apply_ready(patch_payload):
        return "READY"
    if selection_code in {"PATCH_VALIDATION_BLOCKED_SECURITY", "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"}:
        return "SECURITY"
    if gate_status == "FAIL" or selection_code in {
        "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        "PATCH_SEMANTIC_CONFIDENCE_LOW",
    }:
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def _dynamic_template_profile(acceptance_row: dict[str, Any], patch_row: dict[str, Any] | None = None) -> dict[str, Any]:
    dynamic_template = dict((acceptance_row.get("dynamicTemplate") or {}) or {})
    if dynamic_template:
        return {
            "shape_family": str(dynamic_template.get("shapeFamily") or "NONE").strip().upper(),
            "capability_tier": str(dynamic_template.get("capabilityTier") or "NONE").strip().upper(),
            "patch_surface": str(dynamic_template.get("patchSurface") or "NONE").strip().upper(),
            "baseline_family": str(dynamic_template.get("baselineFamily") or "").strip() or None,
            "blocking_reason": str(dynamic_template.get("blockingReason") or "").strip().upper() or None,
            "delivery_class": str(dynamic_template.get("deliveryClass") or "").strip().upper() or None,
        }

    rewrite_facts = dict((acceptance_row.get("rewriteFacts") or {}) or {})
    facts = dict((rewrite_facts.get("dynamicTemplate") or {}) or {})
    profile = dict((facts.get("capabilityProfile") or {}) or {})
    if not facts:
        return {
            "shape_family": "NONE",
            "capability_tier": "NONE",
            "patch_surface": "NONE",
            "baseline_family": None,
            "blocking_reason": None,
            "delivery_class": None,
        }
    capability_tier = str(profile.get("capabilityTier") or "NONE").strip().upper()
    patch_payload = dict(patch_row or {})
    blocking_reason = (
        str(patch_payload.get("dynamicTemplateBlockingReason") or "").strip().upper()
        or str(profile.get("blockerFamily") or "").strip().upper()
        or None
    )
    strategy_type = str((patch_payload.get("dynamicTemplateStrategy") or patch_payload.get("strategyType") or "")).strip().upper()
    delivery_stage = str(patch_payload.get("deliveryStage") or "").strip().upper()
    patch_ready = delivery_stage == "APPLY_READY" if delivery_stage else patch_payload.get("applicable") is True
    delivery_class = None
    if strategy_type.startswith("DYNAMIC_") and patch_ready:
        delivery_class = "READY_DYNAMIC_PATCH"
    elif capability_tier == "SAFE_BASELINE" and blocking_reason and blocking_reason.endswith("NO_EFFECTIVE_DIFF"):
        delivery_class = "SAFE_BASELINE_NO_DIFF"
    elif capability_tier == "SAFE_BASELINE":
        delivery_class = "SAFE_BASELINE_BLOCKED"
    elif str(profile.get("shapeFamily") or "").strip():
        delivery_class = "REVIEW_ONLY"
    return {
        "shape_family": str(profile.get("shapeFamily") or "NONE").strip().upper(),
        "capability_tier": capability_tier,
        "patch_surface": str(profile.get("patchSurface") or "NONE").strip().upper(),
        "baseline_family": str(profile.get("baselineFamily") or "").strip() or None,
        "blocking_reason": blocking_reason,
        "delivery_class": delivery_class,
    }


def _infer_semantic_unupgraded_reason(semantic_gate: dict[str, Any]) -> str | None:
    if not isinstance(semantic_gate, dict):
        return "SEMANTIC_GATE_MISSING"
    if bool(semantic_gate.get("confidenceUpgradeApplied")):
        return None
    hard_conflicts = [str(code or "").strip() for code in (semantic_gate.get("hardConflicts") or []) if str(code or "").strip()]
    if hard_conflicts:
        return f"HARD_CONFLICT:{hard_conflicts[0]}"
    confidence = str(semantic_gate.get("confidence") or "").strip().upper()
    if confidence in {"MEDIUM", "HIGH"}:
        return "ALREADY_CONFIDENT"
    evidence = dict(semantic_gate.get("evidence") or {})
    fingerprint_strength = str(evidence.get("fingerprintStrength") or "").strip().upper()
    row_count_status = str(evidence.get("rowCountStatus") or "").strip().upper()
    if fingerprint_strength in {"EXACT", "PARTIAL"}:
        return "UPGRADE_NOT_NEEDED"
    if row_count_status in {"", "SKIPPED", "ERROR"}:
        return "DB_EVIDENCE_MISSING"
    if fingerprint_strength in {"NONE", "MISMATCH", "MISMATCH_SAMPLE"}:
        return "FINGERPRINT_NOT_MATCHED"
    return "UPGRADE_CRITERIA_NOT_MET"


def _infer_semantic_blocked_reason(acceptance_row: dict[str, Any], semantic_gate: dict[str, Any]) -> str | None:
    status = str(semantic_gate.get("status") or "PASS").strip().upper()
    confidence = str(semantic_gate.get("confidence") or "HIGH").strip().upper()
    if status != "PASS":
        return f"SEMANTIC_GATE_{status}"
    if confidence == "LOW":
        return "VALIDATE_SEMANTIC_CONFIDENCE_LOW"
    acceptance_status = str(acceptance_row.get("status") or "").strip().upper()
    if acceptance_status != "PASS":
        feedback = dict(acceptance_row.get("feedback") or {})
        return str(feedback.get("reason_code") or acceptance_status)
    return None


def compute_verdict(stats: dict[str, Any]) -> str:
    if int(stats.get("fatal_count") or 0) > 0:
        return "BLOCKED"
    if int(stats.get("acceptance_fail") or 0) > 0:
        return "ATTENTION"
    if int(stats.get("acceptance_need_more_params") or 0) > 0:
        return "PARTIAL"
    if int(stats.get("sql_units") or 0) == 0:
        return "EMPTY"
    return "PASS"


def build_sql_rows(units: list[dict[str, Any]], acceptance: list[dict[str, Any]], patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    acceptance_by_sql_key = {str(row.get("sqlKey")): row for row in acceptance}
    patch_by_statement = {str(row.get("statementKey")): row for row in patches}
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "")
        statement_key = sql_key.split("#", 1)[0]
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        perf = acceptance_row.get("perfComparison") or {}
        eq = acceptance_row.get("equivalence") or {}
        semantic_gate = dict(acceptance_row.get("semanticEquivalence") or {})
        semantic_upgrade_applied = bool(semantic_gate.get("confidenceUpgradeApplied"))
        rows.append(
            {
                "sql_key": sql_key,
                "status": acceptance_row.get("status") or "PENDING",
                "selected_source": acceptance_row.get("selectedCandidateSource") or "n/a",
                "semantic_risk": acceptance_row.get("semanticRisk") or "unknown",
                "perf_improved": perf.get("improved"),
                "before_cost": (perf.get("beforeSummary") or {}).get("totalCost"),
                "after_cost": (perf.get("afterSummary") or {}).get("totalCost"),
                "patch_applicable": _patch_apply_ready(patch_row),
                "patch_selection_code": (patch_row.get("selectionReason") or {}).get("code"),
                "rewrite_materialization_mode": (acceptance_row.get("rewriteMaterialization") or {}).get("mode"),
                "rewrite_materialization_reason": (acceptance_row.get("rewriteMaterialization") or {}).get("reasonCode"),
                "row_status": (eq.get("rowCount") or {}).get("status"),
                "evidence_refs": eq.get("evidenceRefs") or [],
                "semantic_gate_status": semantic_gate.get("status") or "UNKNOWN",
                "semantic_gate_confidence": semantic_gate.get("confidence") or "UNKNOWN",
                "semantic_gate_evidence_level": semantic_gate.get("evidenceLevel") or "UNKNOWN",
                "semantic_confidence_before_upgrade": semantic_gate.get("confidenceBeforeUpgrade"),
                "semantic_confidence_upgraded": semantic_upgrade_applied,
                "semantic_upgrade_reasons": semantic_gate.get("confidenceUpgradeReasons") or [],
                "semantic_upgrade_sources": semantic_gate.get("confidenceUpgradeEvidenceSources") or [],
                "semantic_hard_conflicts": semantic_gate.get("hardConflicts") or [],
                "semantic_unupgraded_reason": _infer_semantic_unupgraded_reason(semantic_gate),
                "semantic_blocked_reason": _infer_semantic_blocked_reason(acceptance_row, semantic_gate),
            }
        )
    return rows


def build_proposal_rows(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        issues = proposal.get("issues") or []
        issue_codes = [str(x.get("code")) for x in issues if isinstance(x, dict) and x.get("code")]
        rows.append(
            {
                "sql_key": str(proposal.get("sqlKey") or ""),
                "verdict": str(proposal.get("verdict") or "UNKNOWN"),
                "issue_codes": issue_codes,
                "llm_candidate_count": len(proposal.get(LLM_CANDIDATES_KEY) or []),
            }
        )
    return rows
