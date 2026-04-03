from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..errors import StageError
from ..progress import get_progress_reporter
from ..stages import optimize as optimize_stage
from ..stages import patch_generate as patch_stage
from ..stages import preflight as preflight_stage
from ..stages import report as report_stage
from ..stages import scan as scan_stage
from ..stages import validate as validate_stage
from .finalizer import RunFinalizer
from .phase_handlers import advance_optimize as _phase_advance_optimize
from .phase_handlers import advance_patch_generate as _phase_advance_patch_generate
from .phase_handlers import advance_preflight as _phase_advance_preflight
from .phase_handlers import advance_report as _phase_advance_report
from .phase_handlers import advance_scan as _phase_advance_scan
from .phase_handlers import advance_validate as _phase_advance_validate
from .phase_runtime import record_failure as _record_failure
from .phase_runtime import run_phase_action as _run_phase_action
from .phase_runtime import runtime_cfg as _runtime_cfg
from .requests import AdvanceStepRequest, RunStatusRequest
from .run_selection import selection_scope
from .workflow_definition import (
    PHASE_POLICIES,
    PHASE_TRANSITIONS,
    STAGE_ORDER,
    STATEMENT_PHASE_TARGETS,
)
from .run_repository import RunRepository
from .stage_index import load_index as _load_stage_index
from .status_resolver import ResumeDecision, StatusResolution, StatusResolver
from .workflow_step_runner import build_advance_context as _build_advance_context
from .workflow_step_runner import run_advance_pipeline as _run_advance_pipeline

RunPhaseAction = Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
FinalizeReport = Callable[[Path, dict[str, Any], ContractValidator, dict[str, Any]], bool]
FinalizeWithoutReport = Callable[[Path, dict[str, Any]], None]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]

def _status_resolver() -> StatusResolver:
    return StatusResolver(stage_order=STAGE_ORDER, phase_policies=PHASE_POLICIES)


_STATUS_RESOLVER = _status_resolver()


def _build_run_finalizer() -> RunFinalizer:
    return RunFinalizer(
        report_enabled=report_enabled,
        report_generate=report_stage.generate,
    )


def runs_root(config: dict[str, Any]) -> Path:
    project_root = Path(str(config["project"]["root_path"])).resolve()
    return project_root / "runs"


def next_pending_sql(state: dict[str, Any], phase: str) -> str | None:
    return _STATUS_RESOLVER.next_pending_sql(state, phase)


def pending_by_phase(state: dict[str, Any]) -> dict[str, int]:
    return _STATUS_RESOLVER.pending_by_phase(state)


def report_enabled(config: dict[str, Any]) -> bool:
    return _STATUS_RESOLVER.report_enabled(config)


def report_rebuild_required(state: dict[str, Any]) -> bool:
    return _STATUS_RESOLVER.report_rebuild_required(state)


def is_complete_to_stage(state: dict[str, Any], to_stage: str, *, include_report: bool = False) -> bool:
    return _STATUS_RESOLVER.is_complete_to_stage(state, to_stage, include_report=include_report)


def resolve_report_resume_decision(state: dict[str, Any], to_stage: str, config: dict[str, Any]) -> ResumeDecision | None:
    return _STATUS_RESOLVER.resolve_report_resume_decision(state, to_stage, config)


def resolve_status(request: RunStatusRequest) -> StatusResolution:
    return _STATUS_RESOLVER.resolve_status(request)


def report_phase_complete_for_result(state: dict[str, Any], to_stage: str, config: dict[str, Any]) -> bool:
    return _STATUS_RESOLVER.report_phase_complete_for_result(state, to_stage, config)


def load_index(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    index = _load_stage_index(run_dir)
    return index.units, index.proposals, index.acceptance


def runtime_cfg(config: dict[str, Any], phase: str) -> tuple[int, int, int]:
    return _runtime_cfg(config, phase)


def record_failure(
    run_dir: Path,
    state: dict[str, Any],
    phase: str,
    reason_code: str,
    message: str,
    *,
    repository: RunRepository | None = None,
) -> None:
    _record_failure(
        run_dir,
        state,
        phase,
        reason_code,
        message,
        repository=repository,
    )


def run_phase_action(config: dict[str, Any], phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    return _run_phase_action(config, phase, fn)


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
    finalizer = _build_run_finalizer()
    return finalizer.finalize_report_if_enabled(
        run_dir,
        config,
        validator,
        state,
        final_meta_status=final_meta_status,
        repository=repository,
        run_phase_action_fn=run_phase_action_fn or run_phase_action,
        record_failure_fn=record_failure_fn or record_failure,
    )


def finalize_without_report(
    run_dir: Path,
    state: dict[str, Any],
    *,
    final_meta_status: str,
    repository: RunRepository | None = None,
) -> None:
    finalizer = _build_run_finalizer()
    finalizer.finalize_without_report(
        run_dir,
        state,
        final_meta_status=final_meta_status,
        repository=repository,
    )


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
        "selection_scope": selection_scope(request.plan),
    }


def _mark_updated(state: dict[str, Any]) -> None:
    from datetime import datetime, timezone

    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _complete_phase_result(ctx: Any, phase: str) -> dict[str, Any]:
    return {
        "complete": _STATUS_RESOLVER.is_complete_to_stage(
            ctx.state,
            ctx.to_stage,
            include_report=report_enabled(ctx.config),
        ),
        "phase": phase,
    }


def _finalize_completed_run(ctx: Any) -> None:
    if report_enabled(ctx.config):
        ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status="COMPLETED")
    else:
        ctx.finalize_without(ctx.run_dir, ctx.state, final_meta_status="COMPLETED")


def _handle_phase_failure(ctx: Any, phase: str, exc: StageError) -> None:
    ctx.on_failure(ctx.run_dir, ctx.state, phase, exc.reason_code or "RUNTIME_RETRY_EXHAUSTED", str(exc))
    if report_enabled(ctx.config):
        ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status="FAILED")
    else:
        ctx.repo.set_run_status("FAILED")


def _advance_preflight(ctx: Any) -> dict[str, Any] | None:
    return _phase_advance_preflight(
        ctx,
        phase_transitions=PHASE_TRANSITIONS,
        mark_updated=_mark_updated,
        complete_phase_result=_complete_phase_result,
        finalize_completed_run=_finalize_completed_run,
        handle_phase_failure=_handle_phase_failure,
        preflight_execute=lambda config, run_dir: preflight_stage.execute(config, run_dir),
    )


def _advance_scan(ctx: Any) -> dict[str, Any] | None:
    return _phase_advance_scan(
        ctx,
        phase_transitions=PHASE_TRANSITIONS,
        mark_updated=_mark_updated,
        complete_phase_result=_complete_phase_result,
        finalize_completed_run=_finalize_completed_run,
        handle_phase_failure=_handle_phase_failure,
        scan_execute=lambda config, run_dir, validator: scan_stage.execute(config, run_dir, validator),
    )


def _advance_optimize(ctx: Any, index: Any) -> dict[str, Any] | None:
    return _phase_advance_optimize(
        ctx,
        index,
        phase_transitions=PHASE_TRANSITIONS,
        statement_phase_targets=STATEMENT_PHASE_TARGETS,
        next_pending_sql=next_pending_sql,
        mark_updated=_mark_updated,
        complete_phase_result=_complete_phase_result,
        finalize_completed_run=_finalize_completed_run,
        handle_phase_failure=_handle_phase_failure,
        optimize_execute_one=lambda sql_unit, run_dir, validator: optimize_stage.execute_one(
            sql_unit, run_dir, validator, config=ctx.config
        ),
    )


def _advance_validate(ctx: Any, index: Any) -> dict[str, Any] | None:
    return _phase_advance_validate(
        ctx,
        index,
        phase_transitions=PHASE_TRANSITIONS,
        statement_phase_targets=STATEMENT_PHASE_TARGETS,
        next_pending_sql=next_pending_sql,
        mark_updated=_mark_updated,
        complete_phase_result=_complete_phase_result,
        finalize_completed_run=_finalize_completed_run,
        handle_phase_failure=_handle_phase_failure,
        validate_execute_one=validate_stage.execute_one,
    )


def _advance_patch_generate(ctx: Any, index: Any) -> dict[str, Any] | None:
    return _phase_advance_patch_generate(
        ctx,
        index,
        phase_transitions=PHASE_TRANSITIONS,
        statement_phase_targets=STATEMENT_PHASE_TARGETS,
        next_pending_sql=next_pending_sql,
        mark_updated=_mark_updated,
        complete_phase_result=_complete_phase_result,
        finalize_completed_run=_finalize_completed_run,
        handle_phase_failure=_handle_phase_failure,
        patch_execute_one=patch_stage.execute_one,
    )


def _advance_report(ctx: Any) -> dict[str, Any] | None:
    return _phase_advance_report(
        ctx,
        resolve_report_resume_decision=resolve_report_resume_decision,
        report_enabled=report_enabled,
        report_phase_complete_for_result=report_phase_complete_for_result,
    )


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
    ctx = _build_advance_context(
        request,
        progress=get_progress_reporter(),
        run_phase_action_default=run_phase_action,
        record_failure_default=record_failure,
        finalize_report_default=finalize_report_if_enabled,
        finalize_without_default=finalize_without_report,
    )
    return _run_advance_pipeline(
        ctx,
        pre_index_handlers=PRE_INDEX_HANDLERS,
        indexed_handlers=INDEXED_HANDLERS,
        report_handler=REPORT_HANDLER,
        load_index_fn=load_index,
        complete_phase_result_fn=_complete_phase_result,
    )
