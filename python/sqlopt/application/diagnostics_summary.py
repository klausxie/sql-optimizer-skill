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


def _verify_decision_summary(delivery_assessment: str, evidence_state: str) -> str:
    if evidence_state == "CRITICAL_GAP":
        return "critical verification evidence is incomplete for this output"
    if evidence_state == "DEGRADED":
        return "validation evidence is degraded and should be rechecked before rollout"
    if delivery_assessment == "READY_TO_APPLY":
        return "validated and ready to apply"
    if delivery_assessment == "PATCHABLE_WITH_REWRITE":
        return "validated rewrite exists, but mapper needs template-aware refactoring"
    if delivery_assessment == "MANUAL_REVIEW":
        return "rewrite is promising, but the patch needs manual conflict resolution"
    if delivery_assessment == "NEEDS_REVIEW":
        return "rewrite validated, but patch still needs review"
    return "no ready-to-apply optimization yet"


def _verify_why_now(delivery_assessment: str, evidence_state: str, assessment: dict[str, Any]) -> str:
    if evidence_state == "CRITICAL_GAP":
        return "the main blocker is missing verification evidence, so rollout should wait"
    if bool(assessment.get("db_recheck_recommended")):
        return "the rewrite may be viable, but DB-backed validation needs to be restored first"
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
    has_unverified = str(assessment.get("evidence_state") or "") == "CRITICAL_GAP"
    has_partial = any(str(row.get("status") or "").upper() == "PARTIAL" for row in records)
    delivery_assessment = str(assessment.get("delivery_assessment") or "BLOCKED")
    critical_gaps = list(assessment.get("critical_gaps") or [])
    evidence_state = str(assessment.get("evidence_state") or "NONE")
    decision_summary = _verify_decision_summary(delivery_assessment, evidence_state)
    why_now = _verify_why_now(delivery_assessment, evidence_state, assessment)
    recommended_next_step = _verify_recommended_next_step(run_id, delivery_assessment, assessment)
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
        "delivery_assessment": delivery_assessment,
        "evidence_state": evidence_state,
        "critical_gaps": critical_gaps,
        "decision_summary": decision_summary,
        "why_now": why_now,
        "recommended_next_step": recommended_next_step,
        "warnings": warnings,
        "repair_hints": list(assessment.get("repair_hints") or []),
        "acceptance": acceptance_rows,
        "patches": patch_rows,
        "records": records,
    }
