from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..run_paths import (
    REL_ARTIFACTS_ACCEPTANCE,
    REL_ARTIFACTS_PATCHES,
    REL_ARTIFACTS_PROPOSALS,
    REL_REPORT_JSON,
    canonical_paths,
    to_posix_relative,
)
from ..verification.summary import summarize_records
from .report_metrics import build_failures, build_verification_gate, summarize_failures
from .report_models import ReportArtifacts, ReportInputs, RunReportDocument
from .report_stats import (
    _dynamic_template_profile,
    blocker_family_for_outcome,
    blocker_family_for_patch_row,
    build_proposal_rows,
    build_sql_rows,
    compute_verdict,
)


def _patch_apply_ready(row: dict[str, Any]) -> bool:
    delivery_stage = str(row.get("deliveryStage") or "").strip().upper()
    if delivery_stage:
        return delivery_stage == "APPLY_READY"
    return row.get("applicable") is True


def _normalize_delivery_status(tier: str) -> str:
    normalized = str(tier or "").strip().upper()
    if normalized in {"READY_TO_APPLY", "PATCHABLE_WITH_REWRITE", "MANUAL_REVIEW", "NEEDS_REVIEW", "BLOCKED"}:
        return normalized
    if normalized == "READY":
        return "NEEDS_REVIEW"
    if normalized == "NEEDS_TEMPLATE_REWRITE":
        return "PATCHABLE_WITH_REWRITE"
    return "BLOCKED"


def _aggregation_profile(acceptance_row: dict[str, Any]) -> dict[str, Any]:
    aggregation = dict(((acceptance_row.get("rewriteFacts") or {}).get("aggregationQuery") or {}))
    profile = dict(aggregation.get("capabilityProfile") or {})
    return {
        "shape_family": str(profile.get("shapeFamily") or "NONE").strip().upper() or None,
        "capability_tier": str(profile.get("capabilityTier") or "NONE").strip().upper() or None,
        "constraint_family": str(profile.get("constraintFamily") or "NONE").strip().upper() or None,
        "safe_baseline_family": str(profile.get("safeBaselineFamily") or "").strip() or None,
    }


def _evidence_availability(acceptance_row: dict[str, Any]) -> str | None:
    equivalence = dict(acceptance_row.get("equivalence") or {})
    checked = equivalence.get("checked")
    refs = [str(x) for x in (equivalence.get("evidenceRefs") or []) if str(x).strip()]
    if checked is True and refs:
        return "READY"
    if checked is True:
        return "PARTIAL"
    if checked in {False, None} and acceptance_row:
        return "MISSING"
    return None


def _blocker_primary_code(sql_row: dict[str, Any], acceptance_row: dict[str, Any], patch_row: dict[str, Any]) -> str | None:
    feedback_code = str(((acceptance_row.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code:
        return feedback_code
    selection_code = str((((patch_row.get("selectionReason") or {}).get("code")) or "")).strip()
    if selection_code:
        return selection_code
    semantic_blocked = str(sql_row.get("semantic_blocked_reason") or "").strip()
    return semantic_blocked or None


def _build_sql_artifact_rows(
    *,
    run_dir: Path,
    units: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    sql_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = canonical_paths(run_dir)
    sql_row_by_key = {str(row.get("sql_key") or ""): row for row in sql_rows if str(row.get("sql_key") or "").strip()}
    proposal_by_sql_key = {str(row.get("sqlKey") or ""): row for row in proposals if str(row.get("sqlKey") or "").strip()}
    acceptance_by_sql_key = {str(row.get("sqlKey") or ""): row for row in acceptance if str(row.get("sqlKey") or "").strip()}
    patch_by_statement = {str(row.get("statementKey") or ""): row for row in patches if str(row.get("statementKey") or "").strip()}
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "").strip()
        if not sql_key:
            continue
        statement_key = sql_key.split("#", 1)[0]
        sql_row = sql_row_by_key.get(sql_key, {})
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        proposal_row = proposal_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        aggregation_profile = _aggregation_profile(acceptance_row)
        dynamic_profile = _dynamic_template_profile(acceptance_row, patch_row)
        delivery_tier = str(
            (patch_row.get("deliveryOutcome") or {}).get("tier")
            or (acceptance_row.get("deliveryReadiness") or {}).get("tier")
            or ""
        ).strip()
        if _patch_apply_ready(patch_row):
            delivery_tier = "READY_TO_APPLY"
        delivery_status = _normalize_delivery_status(delivery_tier)
        semantic_gate_status = str(sql_row.get("semantic_gate_status") or "UNKNOWN")
        blocker_primary_code = _blocker_primary_code(sql_row, acceptance_row, patch_row)
        blocker_family = (
            blocker_family_for_patch_row(patch_row, semantic_gate_status=semantic_gate_status)
            if patch_row
            else blocker_family_for_outcome(
                delivery_status=delivery_status,
                blocker_primary_code=blocker_primary_code,
                semantic_gate_status=semantic_gate_status,
            )
        )
        sql_path = to_posix_relative(run_dir, paths.sql_artifact_dir(sql_key))
        trace_path = paths.sql_trace_path(sql_key)
        candidate_generation_diagnostics_path = paths.sql_candidate_generation_diagnostics_path(sql_key)
        evidence_dir = paths.sql_evidence_dir(sql_key)
        rows.append(
            {
                "sql_key": sql_key,
                "statement_key": statement_key,
                "sql_path": sql_path,
                "sql_index": f"{sql_path}/index.json",
                "delivery_status": delivery_status,
                "blocker_primary_code": blocker_primary_code,
                "blocker_family": blocker_family,
                "aggregation_shape_family": aggregation_profile["shape_family"],
                "aggregation_capability_tier": aggregation_profile["capability_tier"],
                "aggregation_constraint_family": aggregation_profile["constraint_family"],
                "aggregation_safe_baseline_family": aggregation_profile["safe_baseline_family"],
                "dynamic_shape_family": dynamic_profile["shape_family"],
                "dynamic_capability_tier": dynamic_profile["capability_tier"],
                "dynamic_patch_surface": dynamic_profile["patch_surface"],
                "dynamic_baseline_family": dynamic_profile["baseline_family"],
                "dynamic_blocking_reason": dynamic_profile["blocking_reason"],
                "dynamic_delivery_class": dynamic_profile["delivery_class"],
                "evidence_availability": _evidence_availability(acceptance_row),
                "artifact_refs": {
                    "report": REL_REPORT_JSON,
                    "acceptance": REL_ARTIFACTS_ACCEPTANCE if acceptance_row else None,
                    "patches": REL_ARTIFACTS_PATCHES if patch_row else None,
                    "proposals": REL_ARTIFACTS_PROPOSALS if proposal_row else None,
                    "verification": None,
                    "trace": f"{sql_path}/trace.optimize.llm.json" if trace_path.exists() else None,
                    "candidate_generation_diagnostics": f"{sql_path}/candidate_generation_diagnostics.json"
                    if candidate_generation_diagnostics_path.exists()
                    else None,
                    "evidence_dir": f"{sql_path}/evidence" if evidence_dir.exists() else None,
                },
            }
        )
    return rows


def _warning_codes(validation_warnings: list[str]) -> list[str]:
    codes: list[str] = []
    for warning in validation_warnings:
        code = str(warning).split(":", 1)[0].strip()
        if code:
            codes.append(code)
    return codes


def _next_action(
    *,
    phase_status: dict[str, Any],
    patch_applicable_count: int,
    blocked_sql_count: int,
    validation_warnings: list[str],
) -> str:
    normalized = {k: str(v or "").strip().upper() for k, v in phase_status.items()}
    incomplete = [status for status in normalized.values() if status in {"PENDING", "RUNNING", "FAILED"}]
    if incomplete and normalized.get("report") != "DONE":
        return "resume"
    if validation_warnings:
        return "inspect"
    if patch_applicable_count > 0 and blocked_sql_count == 0:
        return "apply"
    return "inspect"


def _detailed_next_actions(run_id: str, next_action: str, validation_warnings: list[str]) -> list[dict[str, Any]]:
    if next_action == "apply":
        return [
            {
                "action_id": "apply",
                "title": "Apply generated patches",
                "reason": "safe patches are ready to apply",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id {run_id}"],
            }
        ]
    if next_action == "resume":
        return [
            {
                "action_id": "resume",
                "title": "Resume run",
                "reason": "run has unfinished phases",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id {run_id}"],
            }
        ]
    if validation_warnings:
        return [
            {
                "action_id": "review-evidence",
                "title": "Review verification evidence",
                "reason": "verification warnings are present",
                "commands": [],
            }
        ]
    return [
        {
            "action_id": "inspect",
            "title": "Inspect run outputs",
            "reason": "manual review is required",
            "commands": [],
        }
    ]


def _top_blockers(failure_reason_counts: dict[str, int], validation_warnings: list[str]) -> list[dict[str, Any]]:
    counts = Counter({code: int(count) for code, count in failure_reason_counts.items()})
    counts.update(_warning_codes(validation_warnings))
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"code": code, "count": count} for code, count in ordered[:5]]


def build_report_artifacts(
    run_id: str,
    mode: str,
    config: dict[str, Any],
    run_dir: Path,
    inputs: ReportInputs,
) -> ReportArtifacts:
    del mode, config
    phase_status = dict(inputs.state.phase_status)
    sql_rows = build_sql_rows(inputs.units, inputs.acceptance, inputs.patches)
    proposal_rows = build_proposal_rows(inputs.proposals)
    patch_file_count = sum(len(x.get("patchFiles", [])) for x in inputs.patches)
    patch_applicable_count = sum(1 for x in inputs.patches if _patch_apply_ready(x))
    blocked_sql_count = sum(
        1
        for row in sql_rows
        if str(row.get("status") or "").strip().upper() != "PASS"
        or str(row.get("semantic_gate_status") or "").strip().upper() != "PASS"
        or str(row.get("semantic_gate_confidence") or "").strip().upper() == "LOW"
    )

    failures = build_failures(inputs.acceptance, inputs.manifest_rows)
    failure_reason_counts, _phase_reason_counts, failure_class_counts = summarize_failures(failures)
    verification_summary = summarize_records(run_id, inputs.verification_rows, total_sql=len(inputs.units)).to_contract()
    validation_warnings, evidence_confidence, _verification_gate = build_verification_gate(
        inputs.acceptance,
        inputs.patches,
        inputs.verification_rows,
    )

    sql_artifact_rows = _build_sql_artifact_rows(
        run_dir=run_dir,
        units=inputs.units,
        proposals=inputs.proposals,
        acceptance=inputs.acceptance,
        patches=inputs.patches,
        sql_rows=sql_rows,
    )
    blocker_family_counts = dict(
        Counter(
            str(row.get("blocker_family") or "").strip().upper()
            for row in sql_artifact_rows
            if str(row.get("blocker_family") or "").strip()
        )
    )

    compact_phase_status = dict(phase_status)
    compact_phase_status["report"] = "DONE"
    stats = {
        "sql_units": len(inputs.units),
        "proposals": len(inputs.proposals),
        "acceptance_pass": sum(1 for x in inputs.acceptance if str(x.get("status") or "").strip().upper() == "PASS"),
        "acceptance_fail": sum(1 for x in inputs.acceptance if str(x.get("status") or "").strip().upper() == "FAIL"),
        "acceptance_need_more_params": sum(
            1 for x in inputs.acceptance if str(x.get("status") or "").strip().upper() == "NEED_MORE_PARAMS"
        ),
        "patch_files": patch_file_count,
        "patch_applicable_count": patch_applicable_count,
        "blocked_sql_count": blocked_sql_count,
        "blocker_family_counts": blocker_family_counts,
        "pipeline_coverage": compact_phase_status,
        "fatal_count": failure_class_counts.get("fatal", 0),
    }
    verdict = compute_verdict(stats)
    next_action = _next_action(
        phase_status=compact_phase_status,
        patch_applicable_count=patch_applicable_count,
        blocked_sql_count=blocked_sql_count,
        validation_warnings=validation_warnings,
    )
    next_actions = _detailed_next_actions(run_id, next_action, validation_warnings)
    top_blockers = _top_blockers(failure_reason_counts, validation_warnings)

    report = RunReportDocument(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        target_stage="report",
        status="DONE",
        verdict=verdict,
        next_action=next_action,
        phase_status=compact_phase_status,
        stats=stats,
        top_blockers=top_blockers,
        selection_scope=inputs.state.selection_scope,
        validation_warnings=validation_warnings or None,
        evidence_confidence=evidence_confidence,
    )

    return ReportArtifacts(
        report=report,
        failures=failures,
        state=inputs.state,
        next_actions=next_actions,
        top_blockers=top_blockers,
        sql_rows=sql_rows,
        proposal_rows=proposal_rows,
        diagnostics_sql_outcomes=[],
        diagnostics_sql_artifacts=sql_artifact_rows,
        verification_summary=verification_summary,
        validation_warnings=validation_warnings or None,
        evidence_confidence=evidence_confidence,
    )
