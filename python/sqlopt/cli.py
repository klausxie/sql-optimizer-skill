from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from .application import config_service, run_index, run_service, workflow_engine
from .contracts import ContractValidator
from .error_messages import format_error_message
from .errors import StageError
from .progress import init_progress_reporter
from .verification.explain import action_reason, assess_sql_outcome

STAGE_ORDER = workflow_engine.STAGE_ORDER


def _repo_root() -> Path:
    return run_index.repo_root()


def _legacy_run_index_path() -> Path:
    return run_index.legacy_run_index_path()


def _run_index_path_for_runs_root(runs_root: Path) -> Path:
    return run_index.run_index_path_for_runs_root(runs_root)


def _load_run_index(path: Path) -> dict[str, dict]:
    return run_index.load_run_index(path)


def _save_run_index(path: Path, index: dict[str, dict]) -> None:
    run_index.save_run_index(path, index)


def _remember_run(run_id: str, run_dir: Path, config_path: Path, runs_root: Path) -> None:
    run_index.remember_run(run_id, run_dir, config_path, runs_root)


def _resolve_run_dir(run_id: str) -> Path:
    return run_index.resolve_run_dir(run_id, repo_root_fn=_repo_root)


def _runs_root(config: dict) -> Path:
    return workflow_engine.runs_root(config)


def _next_pending_sql(state: dict, phase: str) -> str | None:
    return workflow_engine.next_pending_sql(state, phase)


def _pending_by_phase(state: dict) -> dict[str, int]:
    return workflow_engine.pending_by_phase(state)


def _report_enabled(config: dict) -> bool:
    return workflow_engine.report_enabled(config)


def _is_complete_to_stage(state: dict, to_stage: str, *, report_enabled: bool = False) -> bool:
    return workflow_engine.is_complete_to_stage(state, to_stage, include_report=report_enabled)


def _load_index(run_dir: Path) -> tuple[dict, dict, dict]:
    return workflow_engine.load_index(run_dir)


def _runtime_cfg(config: dict, phase: str) -> tuple[int, int, int]:
    return workflow_engine.runtime_cfg(config, phase)


def _record_failure(run_dir: Path, state: dict, phase: str, reason_code: str, message: str) -> None:
    workflow_engine.record_failure(run_dir, state, phase, reason_code, message)


def _run_phase_action(config: dict, phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    return workflow_engine.run_phase_action(config, phase, fn)


def _finalize_report_if_enabled(
    run_dir: Path,
    config: dict,
    validator: ContractValidator,
    state: dict,
    *,
    final_meta_status: str,
) -> None:
    workflow_engine.finalize_report_if_enabled(
        run_dir,
        config,
        validator,
        state,
        final_meta_status=final_meta_status,
        run_phase_action_fn=_run_phase_action,
        record_failure_fn=_record_failure,
    )


def _finalize_without_report(run_dir: Path, state: dict, *, final_meta_status: str) -> None:
    workflow_engine.finalize_without_report(run_dir, state, final_meta_status=final_meta_status)


def _advance_one_step(run_dir: Path, config: dict, to_stage: str, validator: ContractValidator) -> dict:
    return workflow_engine.advance_one_step(
        run_dir,
        config,
        to_stage,
        validator,
        run_phase_action_fn=_run_phase_action,
        record_failure_fn=_record_failure,
        finalize_report_if_enabled_fn=_finalize_report_if_enabled,
        finalize_without_report_fn=_finalize_without_report,
    )


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


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
    best_patch = assessment.get("best_patch")
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


def _build_verify_payload(
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
        "repair_hints": list(assessment.get("repair_hints") or []),
        "acceptance": acceptance_rows,
        "patches": patch_rows,
        "records": records,
    }


def _verify_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": payload.get("run_id"),
        "sql_key": payload.get("sql_key"),
        "phase": payload.get("phase"),
        "record_count": payload.get("record_count"),
        "status_counts": payload.get("status_counts"),
        "delivery_assessment": payload.get("delivery_assessment"),
        "evidence_state": payload.get("evidence_state"),
        "decision_summary": payload.get("decision_summary"),
        "why_now": payload.get("why_now"),
        "critical_gaps": payload.get("critical_gaps"),
        "recommended_next_step": payload.get("recommended_next_step"),
        "repair_hints": payload.get("repair_hints"),
    }


def _format_verify_text(payload: dict[str, Any]) -> str:
    status_counts = payload.get("status_counts") or {}
    gaps = payload.get("critical_gaps") or []
    next_step = payload.get("recommended_next_step") or {}
    repair_hints = payload.get("repair_hints") or []
    command = next_step.get("command") or "n/a"
    lines = [
        f"SQL: {payload.get('sql_key')}",
        f"Decision: {payload.get('decision_summary')}",
        f"Why Now: {payload.get('why_now')}",
        f"Delivery: {payload.get('delivery_assessment')}",
        f"Evidence State: {payload.get('evidence_state')}",
        "Evidence: "
        f"VERIFIED={status_counts.get('VERIFIED', 0)} "
        f"PARTIAL={status_counts.get('PARTIAL', 0)} "
        f"UNVERIFIED={status_counts.get('UNVERIFIED', 0)} "
        f"SKIPPED={status_counts.get('SKIPPED', 0)}",
        f"Top Gaps: {', '.join(gaps) if gaps else 'none'}",
    ]
    if repair_hints:
        lines.append(f"Top Hint: {repair_hints[0].get('title')}")
    lines.append(f"Next Step: {next_step.get('action')} ({command})")
    return "\n".join(lines)


def cmd_run(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    try:
        run_id, result = run_service.start_run(config_path, args.to_stage, args.run_id, repo_root=_repo_root())
        print({"run_id": run_id, "result": result})
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        fallback_run_id = args.run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)


def cmd_resume(args: argparse.Namespace) -> None:
    try:
        result = run_service.resume_run(args.run_id, repo_root=_repo_root())
        print({"run_id": args.run_id, "result": result})
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)


def cmd_status(args: argparse.Namespace) -> None:
    try:
        print(run_service.get_status(args.run_id, repo_root=_repo_root()))
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)


def cmd_verify(args: argparse.Namespace) -> None:
    try:
        run_dir = _resolve_run_dir(args.run_id)
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)

    ledger_path = run_dir / "verification" / "ledger.jsonl"
    all_records = _read_jsonl(ledger_path)
    sql_key = str(args.sql_key)
    phase = str(args.phase).strip() if getattr(args, "phase", None) else None
    records = [
        row
        for row in all_records
        if str(row.get("sql_key") or "") == sql_key and (phase is None or str(row.get("phase") or "") == phase)
    ]
    acceptance_rows = [
        row
        for row in _read_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl")
        if str(row.get("sqlKey") or "") == sql_key
    ]
    patch_rows = [
        row
        for row in _read_jsonl(run_dir / "patches" / "patch.results.jsonl")
        if str(row.get("sqlKey") or "") == sql_key
    ]
    payload = _build_verify_payload(
        args.run_id,
        run_dir,
        sql_key,
        phase,
        ledger_path.exists(),
        records,
        acceptance_rows,
        patch_rows,
    )
    output_format = str(getattr(args, "format", "json") or "json").strip().lower()
    if output_format == "text":
        print(_format_verify_text(_verify_summary_payload(payload)))
        return
    if bool(getattr(args, "summary_only", False)):
        print(_verify_summary_payload(payload))
        return
    print(payload)


def cmd_validate_config(args: argparse.Namespace) -> None:
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        error_info = format_error_message("CONFIG_NOT_FOUND", f"Config file not found: {config_path}")
        print({"error": error_info})
        raise SystemExit(2)

    try:
        results = config_service.validate_config(config_path)
        print(results)
        raise SystemExit(0 if results["valid"] else 1)

    except Exception as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print({"error": error_info})
        raise SystemExit(2)


def cmd_apply(args: argparse.Namespace) -> None:
    try:
        print(run_service.apply_run(args.run_id, repo_root=_repo_root()))
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sqlopt",
        description="SQL Optimizer - Analyze and optimize MyBatis SQL statements",
        epilog="For more information, see: https://github.com/your-org/sql-optimizer/docs",
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress messages (only output JSON results)",
    )
    sub = p.add_subparsers(dest="cmd", required=True, help="Available commands")

    p_run = sub.add_parser(
        "run",
        help="Start a new optimization run",
        description="Start a new optimization run from the beginning or a specific stage",
    )
    p_run.add_argument(
        "--config",
        required=True,
        help="Path to sqlopt.yml configuration file",
    )
    p_run.add_argument(
        "--run-id",
        help="Custom run ID (default: auto-generated timestamp-based ID)",
    )
    p_run.add_argument(
        "--to-stage",
        default="patch_generate",
        choices=STAGE_ORDER,
        help="Target stage to run until (default: patch_generate). Stages: " + ", ".join(STAGE_ORDER),
    )
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser(
        "resume",
        help="Resume an existing run",
        description="Resume an existing optimization run from where it left off",
    )
    p_resume.add_argument(
        "--run-id",
        required=True,
        help="Run ID to resume (use 'status' command to list available runs)",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser(
        "status",
        help="Check run status",
        description="Display the current status and progress of an optimization run",
    )
    p_status.add_argument(
        "--run-id",
        required=True,
        help="Run ID to check status for",
    )
    p_status.set_defaults(func=cmd_status)

    p_verify = sub.add_parser(
        "verify",
        help="Inspect verification evidence for one SQL",
        description="Display verification ledger records and related outputs for a single sqlKey",
    )
    p_verify.add_argument(
        "--run-id",
        required=True,
        help="Run ID to inspect",
    )
    p_verify.add_argument(
        "--sql-key",
        required=True,
        help="sqlKey to inspect in the verification ledger",
    )
    p_verify.add_argument(
        "--phase",
        choices=["scan", "optimize", "validate", "patch_generate"],
        help="Optional phase filter for verification records",
    )
    p_verify.add_argument(
        "--summary-only",
        action="store_true",
        help="Return only the compact decision summary instead of full verification records",
    )
    p_verify.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format for verification details (default: json)",
    )
    p_verify.set_defaults(func=cmd_verify)

    p_apply = sub.add_parser(
        "apply",
        help="Apply generated patches",
        description="Apply the generated XML patches to your source files",
    )
    p_apply.add_argument(
        "--run-id",
        required=True,
        help="Run ID whose patches to apply",
    )
    p_apply.set_defaults(func=cmd_apply)

    p_validate = sub.add_parser(
        "validate-config",
        help="Validate configuration file",
        description="Check if the configuration file is valid and complete",
    )
    p_validate.add_argument(
        "--config",
        required=True,
        help="Path to sqlopt.yml configuration file to validate",
    )
    p_validate.set_defaults(func=cmd_validate_config)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    init_progress_reporter(enabled=not getattr(args, "quiet", False))

    start = time.time()
    args.func(args)
    if time.time() - start > 120:
        raise SystemExit("command exceeded 120s budget")
