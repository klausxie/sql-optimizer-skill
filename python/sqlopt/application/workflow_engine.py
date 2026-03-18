from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..progress import get_progress_reporter
from ..stages import diagnose as diagnose_stage
from ..stages import optimize as optimize_stage
from ..stages import patch as apply_stage

from ..stages import scan as scan_stage
from ..stages import validate as validate_stage
from .workflow_facade import ResumeDecision, StatusResolution
from .workflow_facade import (
    build_status_snapshot,
    finalize_report_if_enabled,
    finalize_without_report,
)
from .workflow_facade import (
    is_complete_to_stage,
    load_index,
    next_pending_sql,
    pending_by_phase,
)
from .workflow_facade import (
    record_failure,
    report_enabled,
    report_phase_complete_for_result,
)
from .workflow_facade import (
    report_rebuild_required,
    resolve_report_resume_decision,
    resolve_status,
)
from .workflow_facade import run_phase_action, runs_root, runtime_cfg
from .workflow_definition import (
    PHASE_TRANSITIONS,
    STAGE_ORDER,
    STATEMENT_PHASE_TARGETS,
)
from .requests import AdvanceStepRequest
from .run_repository import RunRepository
from .workflow_handlers_adapter import build_handler_registry as _build_handler_registry
from .workflow_step_runner import build_advance_context as _build_advance_context
from .workflow_step_runner import run_advance_pipeline as _run_advance_pipeline

RunPhaseAction = Callable[
    [dict[str, Any], str, Callable[[], object]], tuple[object, int]
]
FinalizeReport = Callable[
    [Path, dict[str, Any], ContractValidator, dict[str, Any]], bool
]
FinalizeWithoutReport = Callable[[Path, dict[str, Any]], None]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]

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
    diagnose_execute=lambda config, run_dir, validator: diagnose_stage.execute(
        config, run_dir, validator
    ),
    scan_execute=lambda config, run_dir, validator: scan_stage.execute(
        config, run_dir, validator
    ),
    optimize_execute_one=lambda *args, **kwargs: optimize_stage.execute_one(
        *args, **kwargs
    ),
    validate_execute_one=lambda *args, **kwargs: validate_stage.execute_one(
        *args, **kwargs
    ),
    patch_execute_one=lambda *args, **kwargs: apply_stage.execute_one(*args, **kwargs),
)

_complete_phase_result = _HANDLERS.complete_phase_result
_diagnose = _HANDLERS.advance_diagnose
_advance_optimize = _HANDLERS.advance_optimize
_advance_validate = _HANDLERS.advance_validate
_advance_apply = _HANDLERS.advance_apply
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
