from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constants import CONTRACT_VERSION
from ..failure_classification import classify_reason_code
from ..io_utils import read_json
from .report_loader import ReportInputs
from .report_stats import (
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
)

_OPS_TOPOLOGY_STAGE_KEYS = ("scan", "optimize", "validate", "apply", "report")


@dataclass(frozen=True)
class ReportArtifacts:
    report: dict[str, Any]
    topology: dict[str, Any]
    health: dict[str, Any]
    failures: list[dict[str, Any]]
    phase_status: dict[str, Any]
    attempts_by_phase: dict[str, Any]
    next_actions: list[dict[str, Any]]
    top_blockers: list[dict[str, Any]]
    sql_rows: list[dict[str, Any]]
    proposal_rows: list[dict[str, Any]]


def _filter_runtime_policy_for_ops_topology(runtime_cfg: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    timeout_src = dict(runtime_cfg.get("stage_timeout_ms") or {})
    retry_src = dict(runtime_cfg.get("stage_retry_max") or {})
    timeout = {k: int(timeout_src[k]) for k in _OPS_TOPOLOGY_STAGE_KEYS if k in timeout_src}
    retry = {k: int(retry_src[k]) for k in _OPS_TOPOLOGY_STAGE_KEYS if k in retry_src}
    return timeout, retry


def _count_llm_timeouts(run_dir: Path, proposals: list[dict[str, Any]]) -> int:
    count = 0
    for proposal in proposals:
        for ref in proposal.get("llmTraceRefs") or []:
            trace_path = run_dir / ref
            if not trace_path.exists():
                continue
            row = read_json(trace_path)
            if row.get("degrade_reason") == "RUN_TIME_BUDGET_EXHAUSTED":
                count += 1
            if row.get("response", {}).get("error_type") == "TimeoutError":
                count += 1
    return count


def _build_failures(
    acceptance: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in acceptance:
        if row.get("status") == "PASS":
            continue
        code = None
        feedback = row.get("feedback")
        if isinstance(feedback, dict):
            code = feedback.get("reason_code")
        failures.append(
            {
                "sql_key": row.get("sqlKey"),
                "reason_code": code or "VALIDATE_PARAM_INSUFFICIENT",
                "status": row.get("status"),
                "classification": classify_reason_code(code, phase="validate"),
                "phase": "validate",
            }
        )
    for row in manifest_rows:
        if row.get("event") != "failed":
            continue
        payload = row.get("payload") or {}
        reason_code = payload.get("reason_code") or "RUNTIME_RETRY_EXHAUSTED"
        stage = row.get("stage")
        failures.append(
            {
                "sql_key": payload.get("statement_key"),
                "reason_code": reason_code,
                "classification": classify_reason_code(reason_code, phase=stage),
                "status": "FAILED",
                "phase": stage,
            }
        )
    return failures


def _summarize_failures(failures: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, int]]:
    reason_counts: dict[str, int] = {}
    phase_reason_counts: dict[str, dict[str, int]] = {}
    class_counts = {"fatal": 0, "retryable": 0, "degradable": 0}
    for row in failures:
        code = str(row.get("reason_code") or "UNKNOWN")
        reason_counts[code] = reason_counts.get(code, 0) + 1
        phase = str(row.get("phase") or "unknown")
        phase_bucket = phase_reason_counts.setdefault(phase, {})
        phase_bucket[code] = phase_bucket.get(code, 0) + 1
        cls = str(row.get("classification") or "fatal")
        class_counts[cls] = class_counts.get(cls, 0) + 1
    return reason_counts, phase_reason_counts, class_counts


def build_report_artifacts(
    run_id: str,
    mode: str,
    config: dict[str, Any],
    run_dir: Path,
    inputs: ReportInputs,
) -> ReportArtifacts:
    phase_status = dict((inputs.state.get("phase_status") or {}))
    attempts_by_phase = dict((inputs.state.get("attempts_by_phase") or {}))
    llm_enabled = bool(config.get("llm", {}).get("enabled", False))
    llm_generated = sum(len(x.get("llmCandidates", []) or []) for x in inputs.proposals)
    llm_timeout_count = _count_llm_timeouts(run_dir, inputs.proposals)
    perf_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is True
    )
    perf_not_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is False
    )
    patch_file_count = sum(len(x.get("patchFiles", [])) for x in inputs.patches)
    patch_applicable_count = sum(1 for x in inputs.patches if x.get("applicable") is True)
    materialization_counts = materialization_mode_counts(inputs.acceptance)
    materialization_reason_counts_map = materialization_reason_counts(inputs.acceptance)
    materialization_reason_group_counts_map = materialization_reason_group_counts(materialization_reason_counts_map)

    report = {
        "run_id": run_id,
        "mode": mode,
        "llm_gate": {"enabled": llm_enabled} if llm_enabled else None,
        "policy": config["policy"],
        "stats": {
            "sql_units": len(inputs.units),
            "proposals": len(inputs.proposals),
            "acceptance_pass": sum(1 for x in inputs.acceptance if x.get("status") == "PASS"),
            "pass_with_warn_count": sum(1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("warnings") or [])),
            "acceptance_fail": sum(1 for x in inputs.acceptance if x.get("status") == "FAIL"),
            "acceptance_need_more_params": sum(1 for x in inputs.acceptance if x.get("status") == "NEED_MORE_PARAMS"),
            "semantic_error_count": sum(
                1 for x in inputs.acceptance if "VALIDATE_SEMANTIC_ERROR" in ((x.get("perfComparison") or {}).get("reasonCodes") or [])
            ),
            "dollar_substitution_count": sum(1 for x in inputs.acceptance if "DOLLAR_SUBSTITUTION" in (x.get("riskFlags") or [])),
            "patch_files": patch_file_count,
            "patch_applicable_count": patch_applicable_count,
            "materialization_mode_counts": materialization_counts,
            "materialization_reason_counts": materialization_reason_counts_map,
            "materialization_reason_group_counts": materialization_reason_group_counts_map,
            "perf_improved_count": perf_improved_count,
            "perf_compared_but_not_improved_count": perf_not_improved_count,
            "blocked_sql_count": sum(1 for x in inputs.acceptance if x.get("status") != "PASS"),
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
        },
        "items": {
            "units": inputs.units,
            "proposals": inputs.proposals,
            "acceptance": inputs.acceptance,
            "patches": inputs.patches,
        },
        "summary": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": None,
            "release_readiness": None,
            "top_blockers": [],
            "next_actions": [],
            "prioritized_sql_keys": [],
        },
        "contract_version": CONTRACT_VERSION,
    }

    runtime_timeout, runtime_retry = _filter_runtime_policy_for_ops_topology(config["runtime"])
    topology = {
        "run_id": run_id,
        "executor": "python",
        "subagents": {"optimize": False, "validate": False},
        "llm_mode": "enabled" if llm_enabled else "disabled",
        "llm_gate": {"enabled": llm_enabled} if llm_enabled else None,
        "runtime_policy": {
            "resolved_from": "app_config.runtime",
            "stage_timeout_ms": runtime_timeout,
            "stage_retry_max": runtime_retry,
            "stage_retry_backoff_ms": config["runtime"]["stage_retry_backoff_ms"],
        },
    }

    failures = _build_failures(inputs.acceptance, inputs.manifest_rows)
    report["stats"]["preflight_failure_count"] = sum(
        1 for row in inputs.manifest_rows if row.get("stage") == "preflight" and row.get("event") == "failed"
    )
    reason_counts, phase_reason_counts, class_counts = _summarize_failures(failures)
    report["stats"]["ineffective_reason_counts"] = reason_counts
    report["stats"]["phase_reason_code_counts"] = phase_reason_counts
    report["stats"]["fatal_count"] = class_counts.get("fatal", 0)
    report["stats"]["retryable_count"] = class_counts.get("retryable", 0)
    report["stats"]["degradable_count"] = class_counts.get("degradable", 0)
    report["stats"]["pipeline_coverage"] = phase_status

    verdict = compute_verdict(report["stats"])
    readiness = compute_release_readiness(verdict, report["stats"])
    top_blockers = build_top_blockers(failures, reason_counts)
    next_actions = default_next_actions(run_id, verdict, reason_counts)
    prioritized_sql_keys = build_prioritized_sql_keys(failures)

    report["summary"]["verdict"] = verdict
    report["summary"]["release_readiness"] = readiness
    report["summary"]["top_blockers"] = top_blockers
    report["summary"]["next_actions"] = next_actions
    report["summary"]["prioritized_sql_keys"] = prioritized_sql_keys

    sql_rows = build_sql_rows(inputs.units, inputs.acceptance, inputs.patches)
    proposal_rows = build_proposal_rows(inputs.proposals)

    health = {
        "run_id": run_id,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "failure_count": report["stats"]["acceptance_fail"],
        "fatal_failure_count": report["stats"]["fatal_count"],
        "retryable_failure_count": report["stats"]["retryable_count"],
        "degradable_count": report["stats"]["degradable_count"],
        "report_json": str(run_dir / "report.json"),
    }

    return ReportArtifacts(
        report=report,
        topology=topology,
        health=health,
        failures=failures,
        phase_status=phase_status,
        attempts_by_phase=attempts_by_phase,
        next_actions=next_actions,
        top_blockers=top_blockers,
        sql_rows=sql_rows,
        proposal_rows=proposal_rows,
    )
