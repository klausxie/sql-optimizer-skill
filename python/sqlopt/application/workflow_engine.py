from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..errors import StageError
from ..io_utils import read_jsonl
from ..manifest import log_event
from ..progress import get_progress_reporter
from ..runtime import execute_with_retry
from ..stages import optimize as optimize_stage
from ..stages import patch_generate as patch_stage
from ..stages import preflight as preflight_stage
from ..stages import report as report_stage
from ..stages import scan as scan_stage
from ..stages import validate as validate_stage
from .requests import AdvanceStepRequest, RunStatusRequest
from .run_repository import RunRepository

STAGE_ORDER = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]

RunPhaseAction = Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
FinalizeReport = Callable[[Path, dict[str, Any], ContractValidator, dict[str, Any]], bool]
FinalizeWithoutReport = Callable[[Path, dict[str, Any]], None]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]


@dataclass(frozen=True)
class PhaseExecutionPolicy:
    phase: str
    allow_regenerate: bool = False


@dataclass(frozen=True)
class ResumeDecision:
    phase: str
    final_meta_status: str


@dataclass(frozen=True)
class StatusResolution:
    complete: bool
    next_action: str
    current_sql_key: str | None


PHASE_POLICIES = {
    "preflight": PhaseExecutionPolicy("preflight"),
    "scan": PhaseExecutionPolicy("scan"),
    "optimize": PhaseExecutionPolicy("optimize"),
    "validate": PhaseExecutionPolicy("validate"),
    "patch_generate": PhaseExecutionPolicy("patch_generate"),
    "report": PhaseExecutionPolicy("report", allow_regenerate=True),
}

PHASE_TRANSITIONS = {
    "preflight": "scan",
    "scan": "optimize",
    "optimize": "validate",
    "validate": "patch_generate",
    "patch_generate": "report",
    "report": None,
}

STATEMENT_PHASE_TARGETS = {
    "optimize": {"optimize", "validate", "patch_generate", "report"},
    "validate": {"validate", "patch_generate", "report"},
    "patch_generate": {"patch_generate", "report"},
}


@dataclass(frozen=True)
class LoadedStageIndex:
    units: dict[str, Any]
    proposals: dict[str, Any]
    acceptance: dict[str, Any]


@dataclass
class AdvanceContext:
    run_dir: Path
    config: dict[str, Any]
    to_stage: str
    validator: ContractValidator
    repo: RunRepository
    state: dict[str, Any]
    plan: dict[str, Any]
    db_reachable: bool
    progress: Any
    phase_action: RunPhaseAction
    on_failure: RecordFailure
    finalize_report: Callable[..., bool]
    finalize_without: Callable[..., None]


def runs_root(config: dict[str, Any]) -> Path:
    project_root = Path(str(config["project"]["root_path"])).resolve()
    return project_root / "runs"


def next_pending_sql(state: dict[str, Any], phase: str) -> str | None:
    for sql_key, phases in state["statements"].items():
        if phases.get(phase, "PENDING") == "PENDING":
            return sql_key
    return None


def pending_by_phase(state: dict[str, Any]) -> dict[str, int]:
    counts = {"optimize": 0, "validate": 0, "patch_generate": 0}
    for phases in state.get("statements", {}).values():
        for phase in counts:
            if phases.get(phase) == "PENDING":
                counts[phase] += 1
    return counts


def report_enabled(config: dict[str, Any]) -> bool:
    return bool((config.get("report", {}) or {}).get("enabled", True))


def report_rebuild_required(state: dict[str, Any]) -> bool:
    return bool(state.get("report_rebuild_required", False))


def is_complete_to_stage(state: dict[str, Any], to_stage: str, *, include_report: bool = False) -> bool:
    target = "report" if include_report else to_stage
    for phase in STAGE_ORDER:
        status = state["phase_status"].get(phase)
        if phase == target:
            return status == "DONE"
        if status not in {"DONE", "SKIPPED"}:
            return False
    return False


def resolve_report_resume_decision(state: dict[str, Any], to_stage: str, config: dict[str, Any]) -> ResumeDecision | None:
    report_policy = PHASE_POLICIES["report"]
    if report_enabled(config):
        if to_stage == "report" and report_policy.allow_regenerate:
            if not is_complete_to_stage(state, "patch_generate", include_report=False):
                return None
            return ResumeDecision(phase="report", final_meta_status="COMPLETED")
        if is_complete_to_stage(state, to_stage, include_report=False):
            report_status = state["phase_status"].get("report")
            if report_status != "DONE" or report_rebuild_required(state):
                return ResumeDecision(phase="report", final_meta_status="COMPLETED")
        return None

    if to_stage == "report":
        if not is_complete_to_stage(state, "patch_generate", include_report=False):
            return None
        return ResumeDecision(phase="report", final_meta_status="COMPLETED")
    if is_complete_to_stage(state, to_stage, include_report=False) and state["phase_status"].get("report") != "SKIPPED":
        return ResumeDecision(phase="report", final_meta_status="COMPLETED")
    return None


def resolve_status(request: RunStatusRequest) -> StatusResolution:
    report_on = report_enabled(request.config)
    report_status = request.state.get("phase_status", {}).get("report")
    target_stage = request.plan.get("to_stage", "patch_generate")
    report_resume = resolve_report_resume_decision(request.state, target_stage, request.config)
    base_complete = is_complete_to_stage(request.state, target_stage, include_report=report_on)
    report_rebuild = report_rebuild_required(request.state)
    report_done = report_status == "DONE"
    complete = base_complete or (report_on and report_done and report_rebuild and request.meta.get("status") == "COMPLETED")
    if not report_on and report_resume is not None:
        complete = False

    current_phase = request.state.get("current_phase")
    if isinstance(current_phase, str) and current_phase in {"optimize", "validate", "patch_generate"} and not complete:
        current_sql_key = next_pending_sql(request.state, current_phase)
    else:
        current_sql_key = None

    report_action_required = report_resume is not None
    if report_on and target_stage == "report":
        report_action_required = is_complete_to_stage(request.state, "patch_generate", include_report=False) and (
            report_status != "DONE" or report_rebuild
        )

    if report_action_required:
        if report_on and (report_rebuild or report_status != "DONE"):
            next_action = "report-rebuild"
        elif not report_on:
            next_action = "resume"
        else:
            next_action = "report-rebuild"
    elif not complete:
        next_action = "resume"
    else:
        next_action = "none"

    return StatusResolution(complete=complete, next_action=next_action, current_sql_key=current_sql_key)


def report_phase_complete_for_result(state: dict[str, Any], to_stage: str, config: dict[str, Any]) -> bool:
    if report_enabled(config):
        return is_complete_to_stage(state, to_stage, include_report=True)
    return is_complete_to_stage(state, to_stage, include_report=False) and state["phase_status"].get("report") == "SKIPPED"


def load_index(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units = {x["sqlKey"]: x for x in read_jsonl(run_dir / "scan.sqlunits.jsonl")}
    proposals = {x["sqlKey"]: x for x in read_jsonl(run_dir / "proposals" / "optimization.proposals.jsonl")}
    acceptance = {x["sqlKey"]: x for x in read_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl")}
    return units, proposals, acceptance


def runtime_cfg(config: dict[str, Any], phase: str) -> tuple[int, int, int]:
    rt = config["runtime"]
    timeout_ms = int(rt["stage_timeout_ms"][phase])
    retry_max = int(rt["stage_retry_max"][phase])
    retry_backoff_ms = int(rt["stage_retry_backoff_ms"])
    return timeout_ms, retry_max, retry_backoff_ms


def record_failure(
    run_dir: Path,
    state: dict[str, Any],
    phase: str,
    reason_code: str,
    message: str,
    *,
    repository: RunRepository | None = None,
) -> None:
    repo = repository or RunRepository(run_dir)
    state["phase_status"][phase] = "FAILED"
    state["last_error"] = message
    state["last_reason_code"] = reason_code
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo.save_state(state)
    repo.append_step_result(
        phase,
        "FAILED",
        reason_code=reason_code,
        artifact_refs=[str(run_dir / "manifest.jsonl")],
        detail={"message": message},
    )
    log_event(run_dir / "manifest.jsonl", phase, "failed", {"reason_code": reason_code, "message": message})


def run_phase_action(config: dict[str, Any], phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    timeout_ms, retry_max, retry_backoff_ms = runtime_cfg(config, phase)
    return execute_with_retry(
        phase,
        fn,
        timeout_ms=timeout_ms,
        retry_max=retry_max,
        retry_backoff_ms=retry_backoff_ms,
    )


def finalize_report_if_enabled(
    run_dir: Path,
    config: dict[str, Any],
    validator: ContractValidator,
    state: dict[str, Any],
    *,
    final_meta_status: str,
    repository: RunRepository | None = None,
    run_phase_action_fn: RunPhaseAction | None = None,
    record_failure_fn: RecordFailure | None = None,
) -> bool:
    if not report_enabled(config):
        return False
    repo = repository or RunRepository(run_dir)
    phase_action = run_phase_action_fn or run_phase_action
    on_failure = record_failure_fn or record_failure
    report_was_done = state["phase_status"].get("report") == "DONE"
    # Persist the final report phase state before rendering so report artifacts
    # read the same phase coverage that status/state will expose afterwards.
    state["phase_status"]["report"] = "DONE"
    state["current_phase"] = "report"
    state["report_rebuild_required"] = True
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo.save_state(state)
    try:
        _, attempts = phase_action(
            config,
            "report",
            lambda: report_stage.generate(run_dir.name, "analyze", config, run_dir, validator),
        )
    except StageError as exc:
        reason_code = exc.reason_code or "RUNTIME_RETRY_EXHAUSTED"
        if report_was_done:
            state["phase_status"]["report"] = "DONE"
            state["current_phase"] = "report"
            state["last_error"] = str(exc)
            state["last_reason_code"] = reason_code
            state["report_rebuild_required"] = True
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            repo.save_state(state)
            repo.append_step_result(
                "report",
                "FAILED",
                reason_code=reason_code,
                artifact_refs=[str(run_dir / "manifest.jsonl")],
                detail={"message": str(exc), "rebuild": True},
            )
            log_event(run_dir / "manifest.jsonl", "report", "failed", {"reason_code": reason_code, "message": str(exc)})
            repo.set_meta_status(final_meta_status)
            return False

        on_failure(run_dir, state, "report", reason_code, str(exc))
        state["report_rebuild_required"] = True
        state["current_phase"] = "report"
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        repo.save_state(state)
        repo.set_meta_status("READY_TO_FINALIZE" if final_meta_status == "COMPLETED" else final_meta_status)
        return False
    state["attempts_by_phase"]["report"] += attempts
    state["report_rebuild_required"] = False
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo.save_state(state)
    if not report_was_done:
        repo.append_step_result("report", "DONE", artifact_refs=[str(run_dir / "report.json")])
    repo.set_meta_status(final_meta_status)
    return True


def finalize_without_report(
    run_dir: Path,
    state: dict[str, Any],
    *,
    final_meta_status: str,
    repository: RunRepository | None = None,
) -> None:
    repo = repository or RunRepository(run_dir)
    report_was_skipped = state["phase_status"].get("report") == "SKIPPED"
    state["phase_status"]["report"] = "SKIPPED"
    state["report_rebuild_required"] = False
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo.save_state(state)
    if not report_was_skipped:
        repo.append_step_result("report", "SKIPPED")
    repo.set_meta_status(final_meta_status)


def _mark_updated(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _complete_phase_result(ctx: AdvanceContext, phase: str) -> dict[str, Any]:
    return {
        "complete": is_complete_to_stage(ctx.state, ctx.to_stage, include_report=report_enabled(ctx.config)),
        "phase": phase,
    }


def _finalize_completed_run(ctx: AdvanceContext) -> None:
    if report_enabled(ctx.config):
        ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status="COMPLETED")
    else:
        ctx.finalize_without(ctx.run_dir, ctx.state, final_meta_status="COMPLETED")


def _handle_phase_failure(ctx: AdvanceContext, phase: str, exc: StageError) -> None:
    ctx.on_failure(ctx.run_dir, ctx.state, phase, exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
    if report_enabled(ctx.config):
        ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status="FAILED")
    else:
        ctx.repo.set_meta_status("FAILED")


def _advance_preflight(ctx: AdvanceContext) -> dict[str, Any] | None:
    if ctx.state["phase_status"]["preflight"] == "DONE":
        return None
    ctx.progress.report_phase_start("preflight", "Checking configuration and environment")
    try:
        _, attempts = ctx.phase_action(ctx.config, "preflight", lambda: preflight_stage.execute(ctx.config, ctx.run_dir))
        ctx.state["attempts_by_phase"]["preflight"] += attempts
    except StageError as exc:
        _handle_phase_failure(ctx, "preflight", exc)
        raise
    ctx.state["phase_status"]["preflight"] = "DONE"
    ctx.state["current_phase"] = str(PHASE_TRANSITIONS["preflight"])
    _mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result("preflight", "DONE", artifact_refs=[str(ctx.run_dir / "ops" / "preflight.json")])
    ctx.progress.report_phase_complete("preflight")
    if ctx.to_stage == "preflight":
        _finalize_completed_run(ctx)
    return _complete_phase_result(ctx, "preflight")


def _advance_scan(ctx: AdvanceContext) -> dict[str, Any] | None:
    if ctx.state["phase_status"]["scan"] == "DONE":
        return None
    ctx.progress.report_phase_start("scan", "Scanning MyBatis mapper files")
    try:
        units, attempts = ctx.phase_action(ctx.config, "scan", lambda: scan_stage.execute(ctx.config, ctx.run_dir, ctx.validator))
        ctx.state["attempts_by_phase"]["scan"] += attempts
    except StageError as exc:
        _handle_phase_failure(ctx, "scan", exc)
        raise
    ctx.plan["sql_keys"] = [u["sqlKey"] for u in units]
    ctx.repo.set_plan(ctx.plan)
    ctx.state["phase_status"]["scan"] = "DONE"
    ctx.state["current_phase"] = str(PHASE_TRANSITIONS["scan"])
    ctx.state["statements"] = {
        k: {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"} for k in ctx.plan["sql_keys"]
    }
    _mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        "scan",
        "DONE",
        artifact_refs=[str(ctx.run_dir / "scan.sqlunits.jsonl")],
        detail={"sql_keys": ctx.plan["sql_keys"]},
    )
    ctx.progress.report_phase_complete("scan")
    ctx.progress.report_info(f"Found {len(units)} SQL statements to analyze")
    if ctx.to_stage == "scan":
        _finalize_completed_run(ctx)
    return _complete_phase_result(ctx, "scan")


def _advance_optimize(ctx: AdvanceContext, index: LoadedStageIndex) -> dict[str, Any] | None:
    phase = "optimize"
    if ctx.to_stage not in STATEMENT_PHASE_TARGETS[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(PHASE_TRANSITIONS[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_step_result(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["validate"] = "SKIPPED"
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            _finalize_completed_run(ctx)
        return _complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("optimize", "Generating optimization proposals")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            phase,
            lambda: optimize_stage.execute_one(index.units[key], ctx.run_dir, ctx.validator, config=ctx.config),
        )
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        _handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    _mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(ctx.run_dir / "proposals" / "optimization.proposals.jsonl")],
    )
    return {"complete": False, "phase": phase, "sql_key": key}


def _advance_validate(ctx: AdvanceContext, index: LoadedStageIndex) -> dict[str, Any] | None:
    phase = "validate"
    if ctx.to_stage not in STATEMENT_PHASE_TARGETS[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(PHASE_TRANSITIONS[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_step_result(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            _finalize_completed_run(ctx)
        return _complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("validate", "Validating optimized SQL candidates")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            phase,
            lambda: validate_stage.execute_one(
                index.units[key],
                index.proposals.get(key, {}),
                ctx.run_dir,
                ctx.validator,
                db_reachable=ctx.db_reachable,
                config=ctx.config,
            ),
        )
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        _handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    _mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(ctx.run_dir / "acceptance" / "acceptance.results.jsonl")],
    )
    return {"complete": False, "phase": phase, "sql_key": key}


def _advance_patch_generate(ctx: AdvanceContext, index: LoadedStageIndex) -> dict[str, Any] | None:
    phase = "patch_generate"
    if ctx.to_stage not in STATEMENT_PHASE_TARGETS[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(PHASE_TRANSITIONS[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_step_result(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        ctx.repo.set_meta_status("READY_TO_FINALIZE")
        if ctx.to_stage == phase:
            _finalize_completed_run(ctx)
        return _complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("patch_generate", "Generating patch files")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            "apply",
            lambda: patch_stage.execute_one(
                index.units[key],
                index.acceptance.get(key, {"status": "NEED_MORE_PARAMS"}),
                ctx.run_dir,
                ctx.validator,
            ),
        )
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        _handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    _mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(ctx.run_dir / "patches" / "patch.results.jsonl")],
    )
    return {"complete": False, "phase": phase, "sql_key": key}


def _advance_report(ctx: AdvanceContext) -> dict[str, Any] | None:
    report_resume = resolve_report_resume_decision(ctx.state, ctx.to_stage, ctx.config)
    if report_resume is None:
        return None
    if report_enabled(ctx.config):
        report_ok = ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status=report_resume.final_meta_status)
        if ctx.to_stage == "report" and not report_ok:
            raise StageError(
                "report finalization failed",
                reason_code=ctx.state.get("last_reason_code") or "RUNTIME_RETRY_EXHAUSTED",
            )
    else:
        ctx.finalize_without(ctx.run_dir, ctx.state, final_meta_status=report_resume.final_meta_status)
    return {"complete": report_phase_complete_for_result(ctx.state, ctx.to_stage, ctx.config), "phase": report_resume.phase}


PRE_INDEX_HANDLERS = (_advance_preflight, _advance_scan)
INDEXED_HANDLERS = (_advance_optimize, _advance_validate, _advance_patch_generate)
REPORT_HANDLER = _advance_report


def advance_one_step(
    run_dir: Path,
    config: dict[str, Any],
    to_stage: str,
    validator: ContractValidator,
    *,
    repository: RunRepository | None = None,
    run_phase_action_fn: RunPhaseAction | None = None,
    record_failure_fn: RecordFailure | None = None,
    finalize_report_if_enabled_fn: Callable[..., bool] | None = None,
    finalize_without_report_fn: Callable[..., None] | None = None,
) -> dict[str, Any]:
    request = AdvanceStepRequest(
        run_dir=run_dir,
        config=config,
        to_stage=to_stage,
        validator=validator,
        repository=repository,
        run_phase_action_fn=run_phase_action_fn,
        record_failure_fn=record_failure_fn,
        finalize_report_if_enabled_fn=finalize_report_if_enabled_fn,
        finalize_without_report_fn=finalize_without_report_fn,
    )
    return advance_one_step_request(request)


def advance_one_step_request(request: AdvanceStepRequest) -> dict[str, Any]:
    run_dir = request.run_dir
    config = request.config
    to_stage = request.to_stage
    repo = request.repository or RunRepository(run_dir)
    state = repo.load_state()
    plan = repo.get_plan()
    ctx = AdvanceContext(
        run_dir=run_dir,
        config=config,
        to_stage=to_stage,
        validator=request.validator,
        repo=repo,
        state=state,
        plan=plan,
        db_reachable=bool(config.get("validate", {}).get("db_reachable", False)),
        progress=get_progress_reporter(),
        phase_action=request.run_phase_action_fn or run_phase_action,
        on_failure=request.record_failure_fn or record_failure,
        finalize_report=request.finalize_report_if_enabled_fn or finalize_report_if_enabled,
        finalize_without=request.finalize_without_report_fn or finalize_without_report,
    )

    for handler in PRE_INDEX_HANDLERS:
        result = handler(ctx)
        if result is not None:
            return result

    units, proposals, acceptance = load_index(run_dir)
    index = LoadedStageIndex(units=units, proposals=proposals, acceptance=acceptance)
    for handler in INDEXED_HANDLERS:
        result = handler(ctx, index)
        if result is not None:
            return result

    report_result = REPORT_HANDLER(ctx)
    if report_result is not None:
        return report_result

    return _complete_phase_result(ctx, ctx.state["current_phase"])


def build_status_snapshot(request: RunStatusRequest) -> dict[str, Any]:
    status = resolve_status(request)
    pending = [k for k, v in request.state.get("statements", {}).items() if any(x == "PENDING" for x in v.values())]
    return {
        "run_id": request.run_id,
        "current_phase": request.state.get("current_phase"),
        "current_sql_key": status.current_sql_key,
        "phase_status": request.state.get("phase_status"),
        "run_status": request.meta.get("status"),
        "remaining_statements": len(pending),
        "pending_by_phase": pending_by_phase(request.state),
        "attempts_by_phase": request.state.get("attempts_by_phase", {}),
        "last_reason_code": request.state.get("last_reason_code"),
        "complete": status.complete,
        "next_action": status.next_action,
    }
