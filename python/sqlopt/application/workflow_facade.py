from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..stages import report as report_stage
from .workflow_components import build_run_finalizer as _build_run_finalizer
from .workflow_components import build_status_resolver as _build_status_resolver
from .workflow_definition import PHASE_POLICIES, STAGE_ORDER
from .models import ResolvedConfig
from .run_selection import selection_scope
from .phase_runtime import record_failure as _record_failure
from .phase_runtime import run_phase_action as _run_phase_action
from .phase_runtime import runtime_cfg as _runtime_cfg
from .requests import RunStatusRequest
from .run_repository import RunRepository
from .stage_index import load_index as _load_index
from .status_resolver import ResumeDecision, StatusResolution

RunPhaseAction = Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]

_STATUS_RESOLVER = _build_status_resolver(stage_order=STAGE_ORDER, phase_policies=PHASE_POLICIES)


def runs_root(config: ResolvedConfig) -> Path:
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
    index = _load_index(run_dir)
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
    finalizer = _build_run_finalizer(report_enabled=report_enabled, report_generate=report_stage.generate)
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
    finalizer = _build_run_finalizer(report_enabled=report_enabled, report_generate=report_stage.generate)
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
