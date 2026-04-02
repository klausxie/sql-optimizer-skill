from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..progress import get_progress_reporter
from ..stages import optimize as optimize_stage
from ..stages import patch_generate as patch_stage
from ..stages import preflight as preflight_stage
from ..stages import report as report_stage
from ..stages import scan as scan_stage
from ..stages import validate as validate_stage
from .finalizer import RunFinalizer
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
from .workflow_handlers_adapter import build_handler_registry as _build_handler_registry
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

_HANDLERS = _build_handler_registry(
    phase_transitions=PHASE_TRANSITIONS,
    statement_phase_targets=STATEMENT_PHASE_TARGETS,
    next_pending_sql=next_pending_sql,
    report_enabled=report_enabled,
    is_complete_to_stage=lambda state, to_stage, include_report: is_complete_to_stage(
        state, to_stage, include_report=include_report
    ),
    resolve_report_resume_decision=resolve_report_resume_decision,
    report_phase_complete_for_result=report_phase_complete_for_result,
    preflight_execute=lambda config, run_dir: preflight_stage.execute(config, run_dir),
    scan_execute=lambda config, run_dir, validator: scan_stage.execute(config, run_dir, validator),
    optimize_execute_one=lambda *args, **kwargs: optimize_stage.execute_one(*args, **kwargs),
    validate_execute_one=lambda *args, **kwargs: validate_stage.execute_one(*args, **kwargs),
    patch_execute_one=lambda *args, **kwargs: patch_stage.execute_one(*args, **kwargs),
)

_complete_phase_result = _HANDLERS.complete_phase_result
_advance_preflight = _HANDLERS.advance_preflight
_advance_scan = _HANDLERS.advance_scan
_advance_optimize = _HANDLERS.advance_optimize
_advance_validate = _HANDLERS.advance_validate
_advance_patch_generate = _HANDLERS.advance_patch_generate
_advance_report = _HANDLERS.advance_report

PRE_INDEX_HANDLERS = _HANDLERS.pre_index_handlers
INDEXED_HANDLERS = _HANDLERS.indexed_handlers
REPORT_HANDLER = _HANDLERS.report_handler


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
