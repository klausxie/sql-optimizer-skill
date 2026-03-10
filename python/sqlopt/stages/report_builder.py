from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constants import CONTRACT_VERSION
from ..run_paths import (
    REL_DIAGNOSTICS_BLOCKERS_SUMMARY,
    REL_DIAGNOSTICS_SQL_ARTIFACTS,
    REL_DIAGNOSTICS_SQL_OUTCOMES,
    REL_OVERVIEW_REPORT_JSON,
    REL_OVERVIEW_REPORT_MD,
    REL_OVERVIEW_REPORT_SUMMARY_MD,
    REL_PIPELINE_MANIFEST,
    REL_PIPELINE_OPTIMIZE_PROPOSALS,
    REL_PIPELINE_PATCH_RESULTS,
    REL_PIPELINE_SUPERVISOR_STATE,
    REL_PIPELINE_VALIDATE_ACCEPTANCE,
    REL_PIPELINE_VERIFICATION_LEDGER,
    REL_RUN_INDEX_JSON,
    REL_SQL_CATALOG,
    REPORT_RUN_INDEX_OVERVIEW_GROUP,
    REPORT_RUN_INDEX_PIPELINE_GROUP,
    canonical_paths,
    to_posix_relative,
)
from ..verification.summary import summarize_records
from .report_models import (
    OpsHealthDocument,
    OpsTopologyDocument,
    ReportArtifacts,
    ReportInputs,
    RunReportDocument,
    RunReportItems,
    RunReportSummary,
)
from .report_metrics import build_failures
from .report_metrics import summarize_semantic_gates
from .report_metrics import summarize_semantic_gate_quality
from .report_metrics import summarize_semantic_confidence_upgrades
from .report_metrics import build_verification_gate
from .report_metrics import count_llm_timeouts
from .report_metrics import summarize_failures
from .report_stats import (
    build_top_actionable_sql,
    build_prioritized_sql_keys,
    build_proposal_rows,
    build_sql_rows,
    build_top_blockers,
    compute_release_readiness,
    compute_verdict,
    default_next_actions,
    materialization_mode_counts,
    materialization_reason_counts,
    materialization_reason_group_counts,
    report_acceptance_llm_count,
    summarize_actionability,
)

_OPS_TOPOLOGY_STAGE_KEYS = ("scan", "optimize", "validate", "apply", "report")


def _filter_runtime_policy_for_ops_topology(runtime_cfg: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    timeout_src = dict(runtime_cfg.get("stage_timeout_ms") or {})
    retry_src = dict(runtime_cfg.get("stage_retry_max") or {})
    timeout = {k: int(timeout_src[k]) for k in _OPS_TOPOLOGY_STAGE_KEYS if k in timeout_src}
    retry = {k: int(retry_src[k]) for k in _OPS_TOPOLOGY_STAGE_KEYS if k in retry_src}
    return timeout, retry


def _build_sql_artifact_rows(
    *,
    run_dir: Path,
    units: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
    sql_outcomes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = canonical_paths(run_dir)
    outcome_by_sql_key = {str(row.get("sql_key") or ""): row for row in sql_outcomes if str(row.get("sql_key") or "").strip()}
    proposal_by_sql_key = {str(row.get("sqlKey") or ""): row for row in proposals if str(row.get("sqlKey") or "").strip()}
    acceptance_by_sql_key = {str(row.get("sqlKey") or ""): row for row in acceptance if str(row.get("sqlKey") or "").strip()}
    patch_by_statement = {str(row.get("statementKey") or ""): row for row in patches if str(row.get("statementKey") or "").strip()}
    verification_keys = {
        str(row.get("sql_key") or "").strip()
        for row in verification_rows
        if str(row.get("sql_key") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "").strip()
        if not sql_key:
            continue
        statement_key = sql_key.split("#", 1)[0]
        outcome = outcome_by_sql_key.get(sql_key, {})
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        proposal_row = proposal_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        sql_path = to_posix_relative(run_dir, paths.sql_artifact_dir(sql_key))
        trace_path = paths.sql_trace_path(sql_key)
        evidence_dir = paths.sql_evidence_dir(sql_key)
        rows.append(
            {
                "sql_key": sql_key,
                "statement_key": statement_key,
                "sql_path": sql_path,
                "sql_index": f"{sql_path}/index.json",
                "delivery_status": outcome.get("delivery_status") or outcome.get("delivery_tier") or "BLOCKED",
                "blocker_primary_code": outcome.get("blocker_primary_code"),
                "evidence_availability": outcome.get("evidence_availability"),
                "artifact_refs": {
                    "report": REL_OVERVIEW_REPORT_JSON,
                    "acceptance": REL_PIPELINE_VALIDATE_ACCEPTANCE if acceptance_row else None,
                    "patches": REL_PIPELINE_PATCH_RESULTS if patch_row else None,
                    "proposals": REL_PIPELINE_OPTIMIZE_PROPOSALS if proposal_row else None,
                    "verification": REL_PIPELINE_VERIFICATION_LEDGER if sql_key in verification_keys else None,
                    "trace": f"{sql_path}/trace.optimize.llm.json" if trace_path.exists() else None,
                    "evidence_dir": f"{sql_path}/evidence" if evidence_dir.exists() else None,
                },
            }
        )
    return rows


def _build_run_index_payload(
    *,
    run_id: str,
    generated_at: str,
    phase_status: dict[str, Any],
    sql_artifact_rows: list[dict[str, Any]],
    outcome_sql_keys: list[str],
) -> dict[str, Any]:
    def _phase_done(phase: str) -> bool:
        return str(phase_status.get(phase) or "").strip().upper() == "DONE"

    def _sql_row_issues(row: dict[str, Any]) -> tuple[list[str], list[str]]:
        refs = dict(row.get("artifact_refs") or {})
        missing_refs = [key for key, value in refs.items() if not value]
        issues: list[str] = []
        if not refs.get("report"):
            issues.append("MISSING_REPORT_REF")
        if _phase_done("optimize") and not refs.get("proposals"):
            issues.append("MISSING_PROPOSAL_REF")
        if _phase_done("validate") and not refs.get("acceptance"):
            issues.append("MISSING_ACCEPTANCE_REF")
        if _phase_done("patch_generate") and not refs.get("patches"):
            issues.append("MISSING_PATCH_REF")
        if _phase_done("patch_generate") and not refs.get("verification"):
            issues.append("MISSING_VERIFICATION_REF")
        if str(row.get("evidence_availability") or "").strip().upper() == "READY" and not refs.get("evidence_dir"):
            issues.append("READY_EVIDENCE_DIR_MISSING")
        return issues, missing_refs

    sql_keys = [str(row.get("sql_key") or "") for row in sql_artifact_rows if str(row.get("sql_key") or "").strip()]
    alignment_ok = set(sql_keys) == set(str(x) for x in outcome_sql_keys if str(x).strip())
    sql_ref_null_counts: dict[str, int] = {}
    sql_ref_issue_counts: dict[str, int] = {}
    sql_ref_issues: list[dict[str, Any]] = []
    for row in sql_artifact_rows:
        issues, missing_refs = _sql_row_issues(row)
        for ref in missing_refs:
            sql_ref_null_counts[ref] = sql_ref_null_counts.get(ref, 0) + 1
        for issue in issues:
            sql_ref_issue_counts[issue] = sql_ref_issue_counts.get(issue, 0) + 1
        if issues:
            sql_ref_issues.append(
                {
                    "sql_key": str(row.get("sql_key") or ""),
                    "issues": issues,
                    "missing_refs": missing_refs,
                }
            )
    warning_codes: list[str] = []
    if not alignment_ok:
        warning_codes.append("SQL_KEY_ALIGNMENT_MISMATCH")
    warning_codes.extend(sorted(sql_ref_issue_counts.keys()))
    integrity_status = "OK" if not warning_codes else "WARN"
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": generated_at,
        "layout_version": "logical-layered-v3",
        "authoritative": {
            "runtime_state": REL_PIPELINE_SUPERVISOR_STATE,
            "events": REL_PIPELINE_MANIFEST,
            "consumer_summary": [
                REL_OVERVIEW_REPORT_JSON,
                REL_SQL_CATALOG,
                REL_DIAGNOSTICS_SQL_OUTCOMES,
            ],
        },
        "read_order": {
            "human": [
                REL_OVERVIEW_REPORT_SUMMARY_MD,
                REL_OVERVIEW_REPORT_MD,
                REL_DIAGNOSTICS_BLOCKERS_SUMMARY,
                REL_DIAGNOSTICS_SQL_OUTCOMES,
            ],
            "machine": [
                REL_RUN_INDEX_JSON,
                REL_OVERVIEW_REPORT_JSON,
                REL_DIAGNOSTICS_SQL_OUTCOMES,
                REL_SQL_CATALOG,
                REL_PIPELINE_VERIFICATION_LEDGER,
            ],
        },
        "groups": {
            "overview": list(REPORT_RUN_INDEX_OVERVIEW_GROUP),
            "pipeline": list(REPORT_RUN_INDEX_PIPELINE_GROUP),
            "sql": {
                "catalog": REL_SQL_CATALOG,
                "sql_keys": sql_keys,
            },
            "diagnostics": [
                REL_DIAGNOSTICS_SQL_OUTCOMES,
                REL_DIAGNOSTICS_SQL_ARTIFACTS,
                REL_DIAGNOSTICS_BLOCKERS_SUMMARY,
            ],
        },
        "integrity": {
            "status": integrity_status,
            "warning_codes": warning_codes,
            "sql_key_alignment_ok": alignment_ok,
            "sql_artifact_count": len(sql_artifact_rows),
            "sql_ref_null_counts": sql_ref_null_counts,
            "sql_ref_issue_counts": sql_ref_issue_counts,
            "sql_ref_issues": sql_ref_issues,
            "phase_status": phase_status,
        },
    }


def build_report_artifacts(
    run_id: str,
    mode: str,
    config: dict[str, Any],
    run_dir: Path,
    inputs: ReportInputs,
) -> ReportArtifacts:
    phase_status = dict(inputs.state.phase_status)
    llm_enabled = bool(config.get("llm", {}).get("enabled", False))
    llm_generated = sum(len(x.get("llmCandidates", []) or []) for x in inputs.proposals)
    llm_timeout_count = count_llm_timeouts(run_dir, inputs.proposals)
    perf_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is True
    )
    perf_not_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is False
    )
    blocked_sql_count = sum(
        1
        for row in inputs.acceptance
        if str(row.get("status") or "").upper() != "PASS"
        or str(((row.get("semanticEquivalence") or {}).get("status") or "PASS")).upper() != "PASS"
        or str(((row.get("semanticEquivalence") or {}).get("confidence") or "HIGH")).upper() == "LOW"
    )
    patch_file_count = sum(len(x.get("patchFiles", [])) for x in inputs.patches)
    patch_applicable_count = sum(1 for x in inputs.patches if x.get("applicable") is True)
    materialization_counts = materialization_mode_counts(inputs.acceptance)
    materialization_reason_counts_map = materialization_reason_counts(inputs.acceptance)
    materialization_reason_group_counts_map = materialization_reason_group_counts(materialization_reason_counts_map)
    semantic_gate_counts, semantic_gate_reason_counts = summarize_semantic_gates(inputs.acceptance)
    semantic_confidence_distribution, semantic_evidence_level_distribution, semantic_hard_conflict_top_codes = (
        summarize_semantic_gate_quality(inputs.acceptance)
    )
    confidence_upgraded_count, confidence_upgrade_by_evidence_source = summarize_semantic_confidence_upgrades(inputs.acceptance)
    confidence_upgrade_rate = (
        confidence_upgraded_count / len(inputs.acceptance)
        if inputs.acceptance
        else 0.0
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    stats = {
        "sql_units": len(inputs.units),
        "proposals": len(inputs.proposals),
        "acceptance_pass": sum(1 for x in inputs.acceptance if x.get("status") == "PASS"),
        "pass_with_warn_count": sum(1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("warnings") or [])),
        "acceptance_fail": sum(1 for x in inputs.acceptance if x.get("status") == "FAIL"),
        "acceptance_need_more_params": sum(1 for x in inputs.acceptance if x.get("status") == "NEED_MORE_PARAMS"),
        "semantic_error_count": sum(
            1 for x in inputs.acceptance if "VALIDATE_SEMANTIC_ERROR" in ((x.get("perfComparison") or {}).get("reasonCodes") or [])
        ),
        "semantic_gate_pass_count": semantic_gate_counts["pass"],
        "semantic_gate_fail_count": semantic_gate_counts["fail"],
        "semantic_gate_uncertain_count": semantic_gate_counts["uncertain"],
        "semantic_gate_reason_counts": semantic_gate_reason_counts,
        "semantic_confidence_distribution": semantic_confidence_distribution,
        "semantic_evidence_level_distribution": semantic_evidence_level_distribution,
        "semantic_hard_conflict_top_codes": semantic_hard_conflict_top_codes,
        "confidence_upgraded_count": confidence_upgraded_count,
        "confidence_upgrade_rate": round(confidence_upgrade_rate, 4),
        "confidence_upgrade_by_evidence_source": confidence_upgrade_by_evidence_source,
        "dollar_substitution_count": sum(1 for x in inputs.acceptance if "DOLLAR_SUBSTITUTION" in (x.get("riskFlags") or [])),
        "patch_files": patch_file_count,
        "patch_applicable_count": patch_applicable_count,
        "materialization_mode_counts": materialization_counts,
        "materialization_reason_counts": materialization_reason_counts_map,
        "materialization_reason_group_counts": materialization_reason_group_counts_map,
        "perf_improved_count": perf_improved_count,
        "perf_compared_but_not_improved_count": perf_not_improved_count,
        "blocked_sql_count": blocked_sql_count,
        "db_unreachable_count": sum(
            1 for x in inputs.acceptance if "VALIDATE_DB_UNREACHABLE" in (x.get("perfComparison", {}).get("reasonCodes") or [])
        ),
        "llm_candidates_generated": llm_generated,
        "llm_candidates_accepted": report_acceptance_llm_count(inputs.acceptance),
        "llm_candidates_rejected": max(llm_generated - report_acceptance_llm_count(inputs.acceptance), 0),
        "llm_timeout_count": llm_timeout_count,
        "preflight_failure_count": 0,
        "phase_reason_code_counts": {},
        "ineffective_reason_counts": {},
        "fatal_count": 0,
        "retryable_count": 0,
        "degradable_count": 0,
    }

    runtime_timeout, runtime_retry = _filter_runtime_policy_for_ops_topology(config["runtime"])
    topology = OpsTopologyDocument(
        run_id=run_id,
        executor="python",
        subagents={"optimize": False, "validate": False},
        llm_mode="enabled" if llm_enabled else "disabled",
        llm_gate={"enabled": llm_enabled} if llm_enabled else None,
        runtime_policy={
            "resolved_from": "app_config.runtime",
            "stage_timeout_ms": runtime_timeout,
            "stage_retry_max": runtime_retry,
            "stage_retry_backoff_ms": config["runtime"]["stage_retry_backoff_ms"],
        },
    )

    failures = build_failures(inputs.acceptance, inputs.manifest_rows)
    stats["preflight_failure_count"] = sum(
        1 for row in inputs.manifest_rows if row.stage == "preflight" and row.event == "failed"
    )
    reason_counts, phase_reason_counts, class_counts = summarize_failures(failures)
    stats["ineffective_reason_counts"] = reason_counts
    stats["phase_reason_code_counts"] = phase_reason_counts
    stats["fatal_count"] = class_counts.get("fatal", 0)
    stats["retryable_count"] = class_counts.get("retryable", 0)
    stats["degradable_count"] = class_counts.get("degradable", 0)
    stats["pipeline_coverage"] = phase_status
    verification_summary = summarize_records(run_id, inputs.verification_rows, total_sql=len(inputs.units)).to_contract()
    stats["verification"] = {k: v for k, v in verification_summary.items() if k != "generated_at"}
    validation_warnings, evidence_confidence, verification_gate = build_verification_gate(
        inputs.acceptance,
        inputs.patches,
        inputs.verification_rows,
    )
    stats["verification"].update(verification_gate)
    stats["validation_warnings"] = validation_warnings
    stats["evidence_confidence"] = evidence_confidence
    stats["actionability"] = summarize_actionability(inputs.proposals, inputs.acceptance, inputs.patches)
    all_sql_outcomes = build_top_actionable_sql(
        inputs.units,
        inputs.proposals,
        inputs.acceptance,
        inputs.patches,
        inputs.verification_rows,
        limit=None,
    )
    stats["top_actionable_sql"] = all_sql_outcomes[:10]
    sql_artifact_rows = _build_sql_artifact_rows(
        run_dir=run_dir,
        units=inputs.units,
        proposals=inputs.proposals,
        acceptance=inputs.acceptance,
        patches=inputs.patches,
        verification_rows=inputs.verification_rows,
        sql_outcomes=all_sql_outcomes,
    )

    verdict = compute_verdict(stats)
    readiness = compute_release_readiness(verdict, stats)
    failure_rows = [row.to_contract() for row in failures]
    top_blockers = build_top_blockers(failure_rows, reason_counts)
    prioritized_sql_keys = build_prioritized_sql_keys(failure_rows)

    sql_rows = build_sql_rows(inputs.units, inputs.acceptance, inputs.patches)
    proposal_rows = build_proposal_rows(inputs.proposals)
    next_actions = default_next_actions(
        run_id,
        verdict,
        reason_counts,
        top_actionable_sql=stats["top_actionable_sql"],
        verification=stats["verification"],
    )

    report = RunReportDocument(
        run_id=run_id,
        mode=mode,
        llm_gate={"enabled": llm_enabled} if llm_enabled else None,
        policy=config["policy"],
        stats=stats,
        items=RunReportItems(
            units=inputs.units,
            proposals=inputs.proposals,
            acceptance=inputs.acceptance,
            patches=inputs.patches,
        ),
        summary=RunReportSummary(
            generated_at=generated_at,
            verdict=verdict,
            release_readiness=readiness,
            top_blockers=top_blockers,
            next_actions=next_actions,
            prioritized_sql_keys=prioritized_sql_keys,
        ),
        contract_version=CONTRACT_VERSION,
        validation_warnings=validation_warnings or None,
        evidence_confidence=evidence_confidence,
    )

    health = OpsHealthDocument(
        run_id=run_id,
        mode=mode,
        generated_at=generated_at,
        status="ok",
        failure_count=stats["acceptance_fail"],
        fatal_failure_count=stats["fatal_count"],
        retryable_failure_count=stats["retryable_count"],
        degradable_count=stats["degradable_count"],
        report_json=str(run_dir / REL_OVERVIEW_REPORT_JSON),
    )

    return ReportArtifacts(
        report=report,
        topology=topology,
        health=health,
        failures=failures,
        state=inputs.state,
        next_actions=next_actions,
        top_blockers=top_blockers,
        sql_rows=sql_rows,
        proposal_rows=proposal_rows,
        diagnostics_sql_outcomes=all_sql_outcomes,
        diagnostics_sql_artifacts=sql_artifact_rows,
        diagnostics_blockers_summary={
            "run_id": run_id,
            "generated_at": generated_at,
            "top_blockers": top_blockers,
            "reason_counts": reason_counts,
            "phase_reason_code_counts": phase_reason_counts,
            "next_actions": next_actions,
        },
        run_index=_build_run_index_payload(
            run_id=run_id,
            generated_at=generated_at,
            phase_status=phase_status,
            sql_artifact_rows=sql_artifact_rows,
            outcome_sql_keys=[str(row.get("sql_key") or "") for row in all_sql_outcomes],
        ),
        verification_summary=verification_summary,
    )
