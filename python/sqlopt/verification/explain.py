from __future__ import annotations

from typing import Any


def action_reason(action_id: str) -> str:
    normalized = str(action_id or "").strip()
    mapping = {
        "review-evidence": "critical verification evidence is incomplete",
        "check-db": "validation evidence is degraded and needs a DB-backed recheck",
        "restore-db-validation": "validation evidence is degraded and needs a DB-backed recheck",
        "refactor-mapper": "the rewrite is valid, but the mapper needs template-aware refactoring before patch generation",
        "resolve-patch-conflict": "the patch is plausible, but it needs manual conflict resolution",
        "review-patchability": "the rewrite is validated, but the patch still needs manual review",
        "apply": "a validated patch is ready to land",
        "resume": "no ready optimization exists yet, continue the run",
        "remove-dollar": "unsafe SQL substitution blocks optimization",
    }
    return mapping.get(normalized, normalized or "action required")


def delivery_rank(tier: str) -> int:
    normalized = str(tier or "").strip().upper()
    return {
        "READY_TO_APPLY": 4,
        "PATCHABLE_WITH_REWRITE": 3,
        "MANUAL_REVIEW": 2,
        "NEEDS_REVIEW": 1,
        "BLOCKED": 0,
    }.get(normalized, -1)


def best_patch_row(patch_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_rank = -1
    for row in patch_rows:
        delivery_tier = str(((row.get("deliveryOutcome") or {}).get("tier")) or "").strip()
        if not delivery_tier and row.get("applicable") is True:
            delivery_tier = "READY_TO_APPLY"
        rank = delivery_rank(delivery_tier)
        if rank > best_rank:
            best = row
            best_rank = rank
    return best


def best_acceptance_row(acceptance_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_rank = -1
    for row in acceptance_rows:
        decision_layers = dict(row.get("decisionLayers") or {})
        acceptance_layer = dict(decision_layers.get("acceptance") or {})
        delivery_layer = dict(decision_layers.get("delivery") or {})
        status = str(acceptance_layer.get("status") or row.get("status") or "").strip().upper()
        readiness = str(delivery_layer.get("tier") or ((row.get("deliveryReadiness") or {}).get("tier")) or "").strip().upper()
        rank = 0
        if status == "PASS":
            rank += 2
        elif status == "NEED_MORE_PARAMS":
            rank += 1
        if readiness in {"READY_TO_APPLY", "READY"}:
            rank += 2
        elif readiness in {"PATCHABLE_WITH_REWRITE", "NEEDS_TEMPLATE_REWRITE"}:
            rank += 1
        if rank > best_rank:
            best = row
            best_rank = rank
    return best


def critical_gaps(verification_rows: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for row in verification_rows:
        if str(row.get("status") or "").upper() != "UNVERIFIED":
            continue
        code = str(row.get("reason_code") or "").strip()
        if code and code not in gaps:
            gaps.append(code)
    return gaps[:5]


def assess_sql_outcome(
    acceptance_rows: list[dict[str, Any]],
    patch_rows: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    best_patch = best_patch_row(patch_rows)
    best_acceptance = best_acceptance_row(acceptance_rows)
    repair_hints = list((best_patch or {}).get("repairHints") or [])

    if best_patch is not None:
        delivery_tier = str(((best_patch.get("deliveryOutcome") or {}).get("tier")) or "").strip()
        if not delivery_tier and best_patch.get("applicable") is True:
            delivery_tier = "READY_TO_APPLY"
        delivery_assessment = delivery_tier or "BLOCKED"
    elif best_acceptance is not None:
        decision_layers = dict(best_acceptance.get("decisionLayers") or {})
        delivery_layer = dict(decision_layers.get("delivery") or {})
        acceptance_layer = dict(decision_layers.get("acceptance") or {})
        readiness = str(delivery_layer.get("tier") or ((best_acceptance.get("deliveryReadiness") or {}).get("tier")) or "").strip().upper()
        if readiness in {"PATCHABLE_WITH_REWRITE", "NEEDS_TEMPLATE_REWRITE"}:
            delivery_assessment = "PATCHABLE_WITH_REWRITE"
        elif readiness == "READY_TO_APPLY":
            delivery_assessment = "READY_TO_APPLY"
        elif readiness == "READY":
            delivery_assessment = "NEEDS_REVIEW"
        elif str(acceptance_layer.get("status") or best_acceptance.get("status") or "").strip().upper() == "PASS":
            delivery_assessment = "NEEDS_REVIEW"
        else:
            delivery_assessment = "BLOCKED"
    else:
        delivery_assessment = "BLOCKED"

    best_acceptance_layers = dict((best_acceptance or {}).get("decisionLayers") or {})
    evidence_layer = dict(best_acceptance_layers.get("evidence") or {})
    acceptance_layer = dict(best_acceptance_layers.get("acceptance") or {})
    verification_reason_codes = [
        str(row.get("reason_code") or "").strip()
        for row in verification_rows
        if str(row.get("reason_code") or "").strip()
        and str(row.get("status") or "").upper() in {"PARTIAL", "UNVERIFIED"}
    ]
    evidence_reason_codes = [
        str(code).strip()
        for code in (evidence_layer.get("reasonCodes") or [])
        if str(code).strip()
    ]
    gaps = critical_gaps(verification_rows)
    has_partial_verification = any(str(row.get("status") or "").upper() == "PARTIAL" for row in verification_rows)
    degraded = bool(evidence_layer.get("degraded")) or has_partial_verification
    if gaps:
        evidence_state = "CRITICAL_GAP"
    elif degraded:
        evidence_state = "DEGRADED"
    elif acceptance_rows or patch_rows or verification_rows:
        evidence_state = "COMPLETE"
    else:
        evidence_state = "NONE"

    combined_reason_codes = []
    for code in [*evidence_reason_codes, *verification_reason_codes]:
        if code and code not in combined_reason_codes:
            combined_reason_codes.append(code)

    feedback_reason_code = str(acceptance_layer.get("feedbackReasonCode") or ((best_acceptance or {}).get("feedback") or {}).get("reason_code") or "").strip() or None
    db_recheck_recommended = evidence_state == "DEGRADED" and (
        "VALIDATE_DB_UNREACHABLE" in combined_reason_codes or feedback_reason_code == "VALIDATE_PARAM_INSUFFICIENT"
    )

    return {
        "delivery_assessment": delivery_assessment,
        "evidence_state": evidence_state,
        "critical_gaps": gaps,
        "repair_hints": repair_hints,
        "best_patch": best_patch,
        "best_acceptance": best_acceptance,
        "reason_codes": combined_reason_codes,
        "feedback_reason_code": feedback_reason_code,
        "db_recheck_recommended": db_recheck_recommended,
    }
