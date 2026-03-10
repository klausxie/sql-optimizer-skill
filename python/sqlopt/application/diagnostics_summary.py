from __future__ import annotations

from pathlib import Path
from typing import Any

from ..verification.explain import action_reason, assess_sql_outcome


def _verification_status_counts(rows: list[dict]) -> dict[str, int]:
    counts = {"VERIFIED": 0, "PARTIAL": 0, "UNVERIFIED": 0, "SKIPPED": 0}
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if status in counts:
            counts[status] += 1
    return counts


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


def _normalize_delivery_status(tier: str) -> str:
    normalized = str(tier or "").strip().upper()
    if normalized in {"READY_TO_APPLY", "PATCHABLE_WITH_REWRITE", "MANUAL_REVIEW", "NEEDS_REVIEW", "BLOCKED"}:
        return normalized
    if normalized == "READY":
        return "NEEDS_REVIEW"
    if normalized == "NEEDS_TEMPLATE_REWRITE":
        return "PATCHABLE_WITH_REWRITE"
    return "BLOCKED"


def _primary_blocker_message(code: str | None) -> str | None:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return None
    if normalized == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "unsafe ${} dynamic SQL blocks automatic patch generation"
    if normalized == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
        return "semantic confidence is LOW and delivery is blocked until stronger evidence is collected"
    if normalized.startswith("SEMANTIC_GATE_"):
        return "semantic gate is not PASS and blocks downstream patch delivery"
    if normalized == "VERIFICATION_CRITICAL_GAP":
        return "critical verification evidence is missing for this SQL"
    if normalized == "VALIDATE_DB_UNREACHABLE":
        return "database-backed validation is degraded; rerun with healthy connectivity"
    if normalized.startswith("PATCH_"):
        return "patch decision logic blocked automatic delivery for this SQL"
    return normalized


def _pick_primary_blocker(
    *,
    delivery_status: str,
    evidence_state: str,
    critical_gaps: list[str],
    semantic_blocked_reason: str | None,
    acceptance_reason_code: str | None,
    patch_selection_code: str | None,
) -> tuple[str | None, str | None, str | None]:
    code: str | None = None
    phase: str | None = None
    if evidence_state == "CRITICAL_GAP":
        code = str((critical_gaps or [None])[0] or "VERIFICATION_CRITICAL_GAP").strip().upper()
        phase = "verification"
    elif semantic_blocked_reason in {"VALIDATE_SEMANTIC_CONFIDENCE_LOW", "SEMANTIC_GATE_FAIL", "SEMANTIC_GATE_UNCERTAIN"}:
        code = str(semantic_blocked_reason).strip().upper()
        phase = "validate"
    elif acceptance_reason_code:
        code = str(acceptance_reason_code).strip().upper()
        phase = "validate"
    elif patch_selection_code:
        code = str(patch_selection_code).strip().upper()
        phase = "patch_generate"
    elif delivery_status == "BLOCKED":
        code = "DELIVERY_BLOCKED"
        phase = "patch_generate"
    return code, phase, _primary_blocker_message(code)


def _derive_evidence_availability(
    *,
    acceptance_row: dict[str, Any],
    semantic_gate: dict[str, Any],
    evidence_state: str,
    blocker_primary_code: str | None,
) -> tuple[str, str | None, str | None]:
    code = str(blocker_primary_code or "").strip().upper()
    if evidence_state == "CRITICAL_GAP":
        return "MISSING", "CRITICAL_GAP_UNVERIFIED_OUTPUT", "补齐关键验证证据并重跑 report"
    if code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "MISSING", "SKIPPED_BY_SECURITY_BLOCK", "移除 ${} 动态 SQL（改为参数绑定+白名单）后重跑"
    equivalence = dict(acceptance_row.get("equivalence") or {})
    checked = equivalence.get("checked")
    refs = [str(x) for x in (equivalence.get("evidenceRefs") or []) if str(x).strip()]
    evidence_level = str(semantic_gate.get("evidenceLevel") or "").strip().upper()
    if checked is True and refs:
        return "READY", None, None
    if checked is True and evidence_level in {"DB_FINGERPRINT", "DB_COUNT"}:
        return "READY", None, None
    if checked is True:
        return "PARTIAL", "STRUCTURE_ONLY_OR_REFERENCE_MISSING", "补充数据库语义证据（DB_COUNT/DB_FINGERPRINT）"
    if checked is False or checked is None:
        return "MISSING", "SEMANTIC_EVIDENCE_NOT_COLLECTED", "恢复语义校验并重跑 validate"
    return "PARTIAL", "EVIDENCE_STATE_UNCERTAIN", "人工审查 acceptance 与 verification 证据"


def _verify_decision_summary(
    delivery_assessment: str,
    evidence_state: str,
    semantic_blocked_reason: str | None,
    blocker_primary_code: str | None,
) -> str:
    if str(blocker_primary_code or "").strip().upper() == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "unsafe ${} dynamic SQL blocks automatic patch generation until the mapper is rewritten safely"
    if evidence_state == "CRITICAL_GAP":
        return "critical verification evidence is incomplete for this output"
    if evidence_state == "DEGRADED":
        return "validation evidence is degraded and should be rechecked before rollout"
    if semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
        return "semantic confidence is low; stronger DB fingerprint evidence is required before delivery"
    if str(semantic_blocked_reason or "").startswith("SEMANTIC_GATE_"):
        return "semantic gate is blocking delivery; resolve semantic conflicts or uncertainty first"
    if delivery_assessment == "READY_TO_APPLY":
        return "validated and ready to apply"
    if delivery_assessment == "PATCHABLE_WITH_REWRITE":
        return "validated rewrite exists, but mapper needs template-aware refactoring"
    if delivery_assessment == "MANUAL_REVIEW":
        return "rewrite is promising, but the patch needs manual conflict resolution"
    if delivery_assessment == "NEEDS_REVIEW":
        return "rewrite validated, but patch still needs review"
    return "no ready-to-apply optimization yet"


def _verify_why_now(
    delivery_assessment: str,
    evidence_state: str,
    assessment: dict[str, Any],
    semantic_blocked_reason: str | None,
    blocker_primary_code: str | None,
) -> str:
    if str(blocker_primary_code or "").strip().upper() == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "remove ${} risk first, then rerun validation to recover candidate and patch delivery paths"
    if evidence_state == "CRITICAL_GAP":
        return "the main blocker is missing verification evidence, so rollout should wait"
    if bool(assessment.get("db_recheck_recommended")):
        return "the rewrite may be viable, but DB-backed validation needs to be restored first"
    if semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
        return "the main gap is semantic evidence strength, not candidate generation"
    if str(semantic_blocked_reason or "").startswith("SEMANTIC_GATE_"):
        return "semantic gate blockers should be resolved before delivery path decisions"
    if delivery_assessment == "READY_TO_APPLY":
        return "this is the fastest safe win because the patch is already ready"
    if delivery_assessment == "PATCHABLE_WITH_REWRITE":
        return "this becomes high-value as soon as the mapper is refactored for template safety"
    if delivery_assessment == "MANUAL_REVIEW":
        return "the SQL is promising and only manual patch conflict handling remains"
    if delivery_assessment == "NEEDS_REVIEW":
        return "the rewrite is validated, but a human still needs to decide the patch path"
    return "this item still needs stronger validation or a clearer delivery path"


def _verify_recommended_next_step(
    run_id: str,
    delivery_assessment: str,
    assessment: dict[str, Any],
    semantic_blocked_reason: str | None,
    blocker_primary_code: str | None,
) -> dict[str, Any]:
    repair_hints = list(assessment.get("repair_hints") or [])
    primary_hint = repair_hints[0] if repair_hints else {}
    hint_command = primary_hint.get("command")
    if str(assessment.get("evidence_state") or "") == "CRITICAL_GAP":
        return {
            "action": "review-evidence",
            "reason": action_reason("review-evidence"),
            "command": None,
        }
    if bool(assessment.get("db_recheck_recommended")):
        return {
            "action": "restore-db-validation",
            "reason": action_reason("restore-db-validation"),
            "command": None,
        }
    if str(blocker_primary_code or "").strip().upper() == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return {
            "action": "remove-dollar",
            "reason": action_reason("remove-dollar"),
            "command": 'rg -n "\\$\\{" src/main/resources/**/*.xml',
        }
    if semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
        return {
            "action": "review-evidence",
            "reason": action_reason("review-evidence"),
            "command": None,
        }
    if str(semantic_blocked_reason or "").startswith("SEMANTIC_GATE_"):
        return {
            "action": "review-evidence",
            "reason": action_reason("review-evidence"),
            "command": None,
        }
    if delivery_assessment == "READY_TO_APPLY":
        return {
            "action": "apply",
            "reason": action_reason("apply"),
            "command": f"PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id {run_id}",
        }
    if delivery_assessment == "PATCHABLE_WITH_REWRITE":
        return {
            "action": "refactor-mapper",
            "reason": action_reason("refactor-mapper"),
            "command": None,
        }
    if delivery_assessment == "MANUAL_REVIEW":
        return {
            "action": "resolve-patch-conflict",
            "reason": action_reason("resolve-patch-conflict"),
            "command": hint_command,
        }
    if delivery_assessment == "NEEDS_REVIEW":
        return {
            "action": "review-patchability",
            "reason": action_reason("review-patchability"),
            "command": hint_command,
        }
    return {
        "action": "resume",
        "reason": action_reason("resume"),
        "command": f"PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id {run_id}",
    }


def _verify_warnings(assessment: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    reason_codes = [str(code).strip() for code in (assessment.get("reason_codes") or []) if str(code).strip()]
    if "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR" in reason_codes:
        warnings.append(
            "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR: optimize DB evidence hit a SQL syntax error; inspect dbEvidenceSummary.explainError"
        )
    return warnings


def build_verify_payload(
    run_id: str,
    run_dir: Path,
    sql_key: str,
    phase: str | None,
    verification_available: bool,
    records: list[dict],
    acceptance_rows: list[dict],
    patch_rows: list[dict],
) -> dict[str, Any]:
    status_counts = _verification_status_counts(records)
    assessment = assess_sql_outcome(acceptance_rows, patch_rows, records)
    best_acceptance = dict(assessment.get("best_acceptance") or {})
    semantic_gate = dict(best_acceptance.get("semanticEquivalence") or {})
    semantic_blocked_reason = _infer_semantic_blocked_reason(best_acceptance, semantic_gate)
    semantic_unupgraded_reason = _infer_semantic_unupgraded_reason(semantic_gate)
    has_unverified = str(assessment.get("evidence_state") or "") == "CRITICAL_GAP"
    has_partial = any(str(row.get("status") or "").upper() == "PARTIAL" for row in records)
    delivery_assessment = str(assessment.get("delivery_assessment") or "BLOCKED")
    delivery_status = _normalize_delivery_status(delivery_assessment)
    critical_gaps = list(assessment.get("critical_gaps") or [])
    evidence_state = str(assessment.get("evidence_state") or "NONE")
    acceptance_reason_code = str(((best_acceptance.get("feedback") or {}).get("reason_code") or "").strip()) or None
    best_patch = dict(assessment.get("best_patch") or {})
    patch_selection_code = str(((best_patch.get("selectionReason") or {}).get("code") or "")).strip() or None
    blocker_primary_code, blocker_primary_phase, blocker_primary_message = _pick_primary_blocker(
        delivery_status=delivery_status,
        evidence_state=evidence_state,
        critical_gaps=critical_gaps,
        semantic_blocked_reason=semantic_blocked_reason,
        acceptance_reason_code=acceptance_reason_code,
        patch_selection_code=patch_selection_code,
    )
    evidence_availability, evidence_missing_reason, evidence_next_required = _derive_evidence_availability(
        acceptance_row=best_acceptance,
        semantic_gate=semantic_gate,
        evidence_state=evidence_state,
        blocker_primary_code=blocker_primary_code,
    )
    decision_summary = _verify_decision_summary(delivery_status, evidence_state, semantic_blocked_reason, blocker_primary_code)
    why_now = _verify_why_now(delivery_status, evidence_state, assessment, semantic_blocked_reason, blocker_primary_code)
    recommended_next_step = _verify_recommended_next_step(
        run_id,
        delivery_status,
        assessment,
        semantic_blocked_reason,
        blocker_primary_code,
    )
    warnings = _verify_warnings(assessment)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "sql_key": sql_key,
        "phase": phase,
        "verification_available": verification_available,
        "record_count": len(records),
        "status_counts": status_counts,
        "has_unverified": has_unverified,
        "has_partial": has_partial,
        "delivery_status": delivery_status,
        "delivery_assessment": delivery_assessment,
        "evidence_state": evidence_state,
        "evidence_availability": evidence_availability,
        "evidence_missing_reason": evidence_missing_reason,
        "evidence_next_required": evidence_next_required,
        "critical_gaps": critical_gaps,
        "blocker_primary_code": blocker_primary_code,
        "blocker_primary_phase": blocker_primary_phase,
        "blocker_primary_message": blocker_primary_message,
        "decision_summary": decision_summary,
        "why_now": why_now,
        "recommended_next_step": recommended_next_step,
        "warnings": warnings,
        "semantic_gate_status": semantic_gate.get("status") or "UNKNOWN",
        "semantic_gate_confidence": semantic_gate.get("confidence") or "UNKNOWN",
        "semantic_gate_evidence_level": semantic_gate.get("evidenceLevel") or "UNKNOWN",
        "semantic_confidence_before_upgrade": semantic_gate.get("confidenceBeforeUpgrade"),
        "semantic_confidence_upgraded": bool(semantic_gate.get("confidenceUpgradeApplied")),
        "semantic_upgrade_reasons": semantic_gate.get("confidenceUpgradeReasons") or [],
        "semantic_upgrade_sources": semantic_gate.get("confidenceUpgradeEvidenceSources") or [],
        "semantic_hard_conflicts": semantic_gate.get("hardConflicts") or [],
        "semantic_unupgraded_reason": semantic_unupgraded_reason,
        "semantic_blocked_reason": semantic_blocked_reason,
        "repair_hints": list(assessment.get("repair_hints") or []),
        "acceptance": acceptance_rows,
        "patches": patch_rows,
        "records": records,
    }
