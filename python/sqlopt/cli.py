from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .config import load_config
from .contracts import ContractValidator
from .error_messages import format_error_message
from .errors import StageError
from .io_utils import read_json, read_jsonl, write_json
from .manifest import log_event
from .progress import get_progress_reporter, init_progress_reporter
from .runtime import execute_with_retry
from .stages import apply as apply_stage
from .stages import optimize as optimize_stage
from .stages import patch_generate as patch_stage
from .stages import preflight as preflight_stage
from .stages import report as report_stage
from .stages import scan as scan_stage
from .stages import validate as validate_stage
from .supervisor import (
    append_step_result,
    get_plan,
    init_run,
    load_meta,
    load_state,
    save_state,
    set_meta_status,
    set_plan,
)

STAGE_ORDER = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _legacy_run_index_path() -> Path:
    return _repo_root() / ".sqlopt-run-index.json"


def _run_index_path_for_runs_root(runs_root: Path) -> Path:
    return runs_root / "index.json"


def _load_run_index(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_run_index(path: Path, index: dict[str, dict]) -> None:
    write_json(path, index)


def _remember_run(run_id: str, run_dir: Path, config_path: Path, runs_root: Path) -> None:
    index_path = _run_index_path_for_runs_root(runs_root)
    index = _load_run_index(index_path)
    index[run_id] = {
        "run_dir": str(run_dir.resolve()),
        "config_path": str(config_path.resolve()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_run_index(index_path, index)
    legacy_path = _legacy_run_index_path()
    legacy = _load_run_index(legacy_path)
    legacy[run_id] = index[run_id]
    _save_run_index(legacy_path, legacy)


def _resolve_run_dir(run_id: str) -> Path:
    candidates: list[Path] = [_legacy_run_index_path(), *sorted(_repo_root().glob("**/runs/index.json"))]
    for index_path in candidates:
        row = _load_run_index(index_path).get(run_id, {})
        run_dir = Path(str(row.get("run_dir", ""))) if row else Path("")
        if row and run_dir.exists():
            return run_dir
    for meta in _repo_root().glob(f"**/runs/{run_id}/supervisor/meta.json"):
        run_dir = meta.parent.parent
        if run_dir.exists():
            return run_dir
    raise FileNotFoundError(run_id)


def _runs_root(config: dict) -> Path:
    project_root = Path(str(config["project"]["root_path"])).resolve()
    return project_root / "runs"


def _next_pending_sql(state: dict, phase: str) -> str | None:
    for sql_key, phases in state["statements"].items():
        if phases.get(phase, "PENDING") == "PENDING":
            return sql_key
    return None


def _pending_by_phase(state: dict) -> dict[str, int]:
    counts = {"optimize": 0, "validate": 0, "patch_generate": 0}
    for phases in state.get("statements", {}).values():
        for phase in counts:
            if phases.get(phase) == "PENDING":
                counts[phase] += 1
    return counts


def _report_enabled(config: dict) -> bool:
    return bool((config.get("report", {}) or {}).get("enabled", True))


def _is_complete_to_stage(state: dict, to_stage: str, *, report_enabled: bool = False) -> bool:
    target = "report" if report_enabled else to_stage
    for phase in STAGE_ORDER:
        status = state["phase_status"].get(phase)
        if phase == target:
            return status == "DONE"
        if status not in {"DONE", "SKIPPED"}:
            return False
    return False


def _load_index(run_dir: Path) -> tuple[dict, dict, dict]:
    units = {x["sqlKey"]: x for x in read_jsonl(run_dir / "scan.sqlunits.jsonl")}
    proposals = {x["sqlKey"]: x for x in read_jsonl(run_dir / "proposals" / "optimization.proposals.jsonl")}
    acceptance = {x["sqlKey"]: x for x in read_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl")}
    return units, proposals, acceptance


def _runtime_cfg(config: dict, phase: str) -> tuple[int, int, int]:
    rt = config["runtime"]
    timeout_ms = int(rt["stage_timeout_ms"][phase])
    retry_max = int(rt["stage_retry_max"][phase])
    retry_backoff_ms = int(rt["stage_retry_backoff_ms"])
    return timeout_ms, retry_max, retry_backoff_ms


def _record_failure(run_dir: Path, state: dict, phase: str, reason_code: str, message: str) -> None:
    state["phase_status"][phase] = "FAILED"
    state["last_error"] = message
    state["last_reason_code"] = reason_code
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(run_dir, state)
    append_step_result(
        run_dir,
        phase,
        "FAILED",
        reason_code=reason_code,
        artifact_refs=[str(run_dir / "manifest.jsonl")],
        detail={"message": message},
    )
    log_event(run_dir / "manifest.jsonl", phase, "failed", {"reason_code": reason_code, "message": message})


def _run_phase_action(config: dict, phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    timeout_ms, retry_max, retry_backoff_ms = _runtime_cfg(config, phase)
    return execute_with_retry(
        phase,
        fn,
        timeout_ms=timeout_ms,
        retry_max=retry_max,
        retry_backoff_ms=retry_backoff_ms,
    )


def _finalize_report_if_enabled(
    run_dir: Path,
    config: dict,
    validator: ContractValidator,
    state: dict,
    *,
    final_meta_status: str,
) -> None:
    if not _report_enabled(config):
        return
    try:
        _, attempts = _run_phase_action(
            config,
            "report",
            lambda: report_stage.generate(run_dir.name, "analyze", config, run_dir, validator),
        )
    except StageError as exc:
        _record_failure(run_dir, state, "report", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
        return
    state["attempts_by_phase"]["report"] += attempts
    state["phase_status"]["report"] = "DONE"
    state["current_phase"] = "report"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(run_dir, state)
    append_step_result(run_dir, "report", "DONE", artifact_refs=[str(run_dir / "report.json")])
    set_meta_status(run_dir, final_meta_status)


def _finalize_without_report(run_dir: Path, state: dict, *, final_meta_status: str) -> None:
    state["phase_status"]["report"] = "SKIPPED"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(run_dir, state)
    append_step_result(run_dir, "report", "SKIPPED")
    set_meta_status(run_dir, final_meta_status)


def _advance_one_step(run_dir: Path, config: dict, to_stage: str, validator: ContractValidator) -> dict:
    state = load_state(run_dir)
    plan = get_plan(run_dir)
    db_reachable = bool(config.get("validate", {}).get("db_reachable", False))
    progress = get_progress_reporter()

    if state["phase_status"]["preflight"] != "DONE":
        progress.report_phase_start("preflight", "Checking configuration and environment")
        try:
            _, attempts = _run_phase_action(config, "preflight", lambda: preflight_stage.execute(config, run_dir))
            state["attempts_by_phase"]["preflight"] += attempts
        except StageError as exc:
            _record_failure(run_dir, state, "preflight", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="FAILED")
            else:
                set_meta_status(run_dir, "FAILED")
            raise
        state["phase_status"]["preflight"] = "DONE"
        state["current_phase"] = "scan"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_dir, state)
        append_step_result(
            run_dir,
            "preflight",
            "DONE",
            artifact_refs=[str(run_dir / "ops" / "preflight.json")],
        )
        progress.report_phase_complete("preflight")
        if to_stage == "preflight":
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
            else:
                _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
        return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": "preflight"}

    if state["phase_status"]["scan"] != "DONE":
        progress.report_phase_start("scan", "Scanning MyBatis mapper files")
        try:
            units, attempts = _run_phase_action(config, "scan", lambda: scan_stage.execute(config, run_dir, validator))
            state["attempts_by_phase"]["scan"] += attempts
        except StageError as exc:
            _record_failure(run_dir, state, "scan", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="FAILED")
            else:
                set_meta_status(run_dir, "FAILED")
            raise
        plan["sql_keys"] = [u["sqlKey"] for u in units]
        set_plan(run_dir, plan)
        state["phase_status"]["scan"] = "DONE"
        state["current_phase"] = "optimize"
        state["statements"] = {k: {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"} for k in plan["sql_keys"]}
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_dir, state)
        append_step_result(
            run_dir,
            "scan",
            "DONE",
            artifact_refs=[str(run_dir / "scan.sqlunits.jsonl")],
            detail={"sql_keys": plan["sql_keys"]},
        )
        progress.report_phase_complete("scan")
        progress.report_info(f"Found {len(units)} SQL statements to analyze")
        if to_stage == "scan":
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
            else:
                _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
        return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": "scan"}

    units, proposals, acceptance = _load_index(run_dir)

    if to_stage in ("optimize", "validate", "patch_generate", "report") and state["phase_status"]["optimize"] != "DONE":
        key = _next_pending_sql(state, "optimize")
        if key is None:
            state["phase_status"]["optimize"] = "DONE"
            state["current_phase"] = "validate"
            save_state(run_dir, state)
            append_step_result(run_dir, "optimize", "DONE")
            progress.report_phase_complete("optimize")
            if to_stage == "optimize":
                state["phase_status"]["validate"] = "SKIPPED"
                state["phase_status"]["patch_generate"] = "SKIPPED"
                save_state(run_dir, state)
                if _report_enabled(config):
                    _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
                else:
                    _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
            return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": "optimize"}

        # Report progress for optimize phase
        total_statements = len(plan["sql_keys"])
        completed = sum(1 for v in state["statements"].values() if v.get("optimize") == "DONE")
        current_index = completed + 1
        progress.report_statement_progress(current_index, total_statements, key)

        try:
            _, attempts = _run_phase_action(
                config,
                "optimize",
                lambda: optimize_stage.execute_one(units[key], run_dir, validator, config=config),
            )
            state["attempts_by_phase"]["optimize"] += attempts
        except StageError as exc:
            _record_failure(run_dir, state, "optimize", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="FAILED")
            else:
                set_meta_status(run_dir, "FAILED")
            raise
        state["statements"][key]["optimize"] = "DONE"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_dir, state)
        append_step_result(
            run_dir,
            "optimize",
            "DONE",
            sql_key=key,
            artifact_refs=[str(run_dir / "proposals" / "optimization.proposals.jsonl")],
        )
        return {"complete": False, "phase": "optimize", "sql_key": key}

    if to_stage in ("validate", "patch_generate", "report") and state["phase_status"]["validate"] != "DONE":
        key = _next_pending_sql(state, "validate")
        if key is None:
            state["phase_status"]["validate"] = "DONE"
            state["current_phase"] = "patch_generate"
            save_state(run_dir, state)
            append_step_result(run_dir, "validate", "DONE")
            if to_stage == "validate":
                state["phase_status"]["patch_generate"] = "SKIPPED"
                save_state(run_dir, state)
                if _report_enabled(config):
                    _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
                else:
                    _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
            return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": "validate"}
        try:
            _, attempts = _run_phase_action(
                config,
                "validate",
                lambda: validate_stage.execute_one(
                    units[key],
                    proposals.get(key, {}),
                    run_dir,
                    validator,
                    db_reachable=db_reachable,
                    config=config,
                ),
            )
            state["attempts_by_phase"]["validate"] += attempts
        except StageError as exc:
            _record_failure(run_dir, state, "validate", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="FAILED")
            else:
                set_meta_status(run_dir, "FAILED")
            raise
        state["statements"][key]["validate"] = "DONE"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_dir, state)
        append_step_result(
            run_dir,
            "validate",
            "DONE",
            sql_key=key,
            artifact_refs=[str(run_dir / "acceptance" / "acceptance.results.jsonl")],
        )
        return {"complete": False, "phase": "validate", "sql_key": key}

    if to_stage in ("patch_generate", "report") and state["phase_status"]["patch_generate"] != "DONE":
        key = _next_pending_sql(state, "patch_generate")
        if key is None:
            state["phase_status"]["patch_generate"] = "DONE"
            state["current_phase"] = "report"
            save_state(run_dir, state)
            append_step_result(run_dir, "patch_generate", "DONE")
            set_meta_status(run_dir, "READY_TO_FINALIZE")
            if to_stage == "patch_generate":
                if _report_enabled(config):
                    _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
                else:
                    _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
            return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": "patch_generate"}
        try:
            _, attempts = _run_phase_action(
                config,
                "apply",
                lambda: patch_stage.execute_one(units[key], acceptance.get(key, {"status": "NEED_MORE_PARAMS"}), run_dir, validator),
            )
            state["attempts_by_phase"]["patch_generate"] += attempts
        except StageError as exc:
            _record_failure(run_dir, state, "patch_generate", exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
            if _report_enabled(config):
                _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="FAILED")
            else:
                set_meta_status(run_dir, "FAILED")
            raise
        state["statements"][key]["patch_generate"] = "DONE"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_dir, state)
        append_step_result(
            run_dir,
            "patch_generate",
            "DONE",
            sql_key=key,
            artifact_refs=[str(run_dir / "patches" / "patch.results.jsonl")],
        )
        return {"complete": False, "phase": "patch_generate", "sql_key": key}

    if to_stage == "report":
        if _report_enabled(config):
            _finalize_report_if_enabled(run_dir, config, validator, state, final_meta_status="COMPLETED")
            if state["phase_status"]["report"] != "DONE":
                raise StageError("report finalization failed", reason_code="RUNTIME_RETRY_EXHAUSTED")
        else:
            _finalize_without_report(run_dir, state, final_meta_status="COMPLETED")
        return {"complete": True, "phase": "report"}

    return {"complete": _is_complete_to_stage(state, to_stage, report_enabled=_report_enabled(config)), "phase": state["current_phase"]}


def cmd_run(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    config = load_config(config_path)
    run_id = args.run_id or f"run_{uuid4().hex[:12]}"
    runs_root = _runs_root(config)
    run_dir = runs_root / run_id
    if not run_dir.exists():
        init_run(run_dir, config, run_id)
        write_json(run_dir / "config.resolved.json", config)
        log_event(run_dir / "manifest.jsonl", "initialize", "done", {"run_id": run_id})
    _remember_run(run_id, run_dir, config_path, runs_root)
    set_meta_status(run_dir, "RUNNING")

    plan = get_plan(run_dir)
    plan["to_stage"] = args.to_stage
    set_plan(run_dir, plan)

    validator = ContractValidator(_repo_root())
    try:
        result = _advance_one_step(run_dir, config, args.to_stage, validator)
        print({"run_id": run_id, "result": result})
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        print({"run_id": run_id, "error": error_info})
        raise SystemExit(2)


def cmd_resume(args: argparse.Namespace) -> None:
    try:
        run_dir = _resolve_run_dir(args.run_id)
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)
    config = load_config(run_dir / "config.resolved.json")
    plan = get_plan(run_dir)
    validator = ContractValidator(_repo_root())
    try:
        result = _advance_one_step(run_dir, config, plan.get("to_stage", "patch_generate"), validator)
        print({"run_id": args.run_id, "result": result})
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)


def cmd_status(args: argparse.Namespace) -> None:
    try:
        run_dir = _resolve_run_dir(args.run_id)
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)
    state = load_state(run_dir)
    plan = get_plan(run_dir)
    meta = load_meta(run_dir)
    config = load_config(run_dir / "config.resolved.json")
    complete = _is_complete_to_stage(state, plan.get("to_stage", "patch_generate"), report_enabled=_report_enabled(config))
    pending = [k for k, v in state.get("statements", {}).items() if any(x == "PENDING" for x in v.values())]
    current_phase = state.get("current_phase")
    if isinstance(current_phase, str) and current_phase in {"optimize", "validate", "patch_generate"} and not complete:
        current_sql_key = _next_pending_sql(state, current_phase)
    else:
        current_sql_key = None
    print({
        "run_id": args.run_id,
        "current_phase": current_phase,
        "current_sql_key": current_sql_key,
        "phase_status": state.get("phase_status"),
        "run_status": meta.get("status"),
        "remaining_statements": len(pending),
        "pending_by_phase": _pending_by_phase(state),
        "attempts_by_phase": state.get("attempts_by_phase", {}),
        "last_reason_code": state.get("last_reason_code"),
        "complete": complete,
        "next_action": "resume" if not complete else "report-ready",
    })


def cmd_validate_config(args: argparse.Namespace) -> None:
    """Validate configuration file."""
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        error_info = format_error_message("CONFIG_NOT_FOUND", f"Config file not found: {config_path}")
        print({"error": error_info})
        raise SystemExit(2)

    try:
        config = load_config(config_path)

        # Validation results
        results = {
            "valid": True,
            "config_path": str(config_path),
            "checks": []
        }

        # Check required fields
        required_fields = [
            ("project", "root_path"),
            ("scan", "mapper_globs"),
            ("db", "platform"),
            ("db", "dsn"),
        ]

        for *path, field in required_fields:
            current = config
            field_path = ".".join(path + [field])
            try:
                for key in path:
                    current = current[key]
                if field in current:
                    results["checks"].append({
                        "field": field_path,
                        "status": "ok",
                        "value": str(current[field])[:50]  # Truncate long values
                    })
                else:
                    results["checks"].append({
                        "field": field_path,
                        "status": "missing",
                        "message": "Required field is missing"
                    })
                    results["valid"] = False
            except (KeyError, TypeError):
                results["checks"].append({
                    "field": field_path,
                    "status": "missing",
                    "message": "Parent section is missing"
                })
                results["valid"] = False

        # Check for placeholders
        dsn = config.get("db", {}).get("dsn", "")
        if "<" in dsn or ">" in dsn:
            results["checks"].append({
                "field": "db.dsn",
                "status": "warning",
                "message": "DSN contains placeholders, please replace with actual values"
            })

        jar_path = config.get("scan", {}).get("java_scanner", {}).get("jar_path", "")
        if jar_path == "__SCANNER_JAR__":
            results["checks"].append({
                "field": "scan.java_scanner.jar_path",
                "status": "warning",
                "message": "JAR path is placeholder, run install_skill.py to fix"
            })

        # Check mapper files exist
        mapper_globs = config.get("scan", {}).get("mapper_globs", [])
        if mapper_globs:
            project_root = Path(config.get("project", {}).get("root_path", ".")).resolve()
            import glob as glob_module
            found_files = []
            for pattern in mapper_globs:
                full_pattern = str(project_root / pattern)
                matches = glob_module.glob(full_pattern, recursive=True)
                found_files.extend(matches)

            results["checks"].append({
                "field": "scan.mapper_globs",
                "status": "ok" if found_files else "warning",
                "message": f"Found {len(found_files)} mapper file(s)" if found_files else "No mapper files found"
            })

        print(results)
        raise SystemExit(0 if results["valid"] else 1)

    except Exception as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print({"error": error_info})
        raise SystemExit(2)


def cmd_apply(args: argparse.Namespace) -> None:
    try:
        run_dir = _resolve_run_dir(args.run_id)
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": args.run_id, "error": error_info})
        raise SystemExit(2)
    state = apply_stage.apply_from_config(run_dir)
    print({"run_id": args.run_id, "apply": state})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sqlopt",
        description="SQL Optimizer - Analyze and optimize MyBatis SQL statements",
        epilog="For more information, see: https://github.com/your-org/sql-optimizer/docs"
    )
    p.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages (only output JSON results)"
    )
    sub = p.add_subparsers(dest="cmd", required=True, help="Available commands")

    # run command
    p_run = sub.add_parser(
        "run",
        help="Start a new optimization run",
        description="Start a new optimization run from the beginning or a specific stage"
    )
    p_run.add_argument(
        "--config",
        required=True,
        help="Path to sqlopt.yml configuration file"
    )
    p_run.add_argument(
        "--run-id",
        help="Custom run ID (default: auto-generated timestamp-based ID)"
    )
    p_run.add_argument(
        "--to-stage",
        default="patch_generate",
        choices=STAGE_ORDER,
        help="Target stage to run until (default: patch_generate). Stages: " + ", ".join(STAGE_ORDER)
    )
    p_run.set_defaults(func=cmd_run)

    # resume command
    p_resume = sub.add_parser(
        "resume",
        help="Resume an existing run",
        description="Resume an existing optimization run from where it left off"
    )
    p_resume.add_argument(
        "--run-id",
        required=True,
        help="Run ID to resume (use 'status' command to list available runs)"
    )
    p_resume.set_defaults(func=cmd_resume)

    # status command
    p_status = sub.add_parser(
        "status",
        help="Check run status",
        description="Display the current status and progress of an optimization run"
    )
    p_status.add_argument(
        "--run-id",
        required=True,
        help="Run ID to check status for"
    )
    p_status.set_defaults(func=cmd_status)

    # apply command
    p_apply = sub.add_parser(
        "apply",
        help="Apply generated patches",
        description="Apply the generated XML patches to your source files"
    )
    p_apply.add_argument(
        "--run-id",
        required=True,
        help="Run ID whose patches to apply"
    )
    p_apply.set_defaults(func=cmd_apply)

    # validate-config command
    p_validate = sub.add_parser(
        "validate-config",
        help="Validate configuration file",
        description="Check if the configuration file is valid and complete"
    )
    p_validate.add_argument(
        "--config",
        required=True,
        help="Path to sqlopt.yml configuration file to validate"
    )
    p_validate.set_defaults(func=cmd_validate_config)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize progress reporter based on --quiet flag
    init_progress_reporter(enabled=not getattr(args, 'quiet', False))

    start = time.time()
    args.func(args)
    if time.time() - start > 120:
        raise SystemExit("command exceeded 120s budget")
