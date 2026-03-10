from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from .models import ResolvedConfig, RunPlan, RunState
from .requests import AdvanceStepRequest
from .run_repository import RunRepository
from .stage_index import LoadedStageIndex


@dataclass
class AdvanceContext:
    run_dir: Path
    config: ResolvedConfig
    to_stage: str
    validator: ContractValidator
    repo: RunRepository
    state: RunState
    plan: RunPlan
    db_reachable: bool
    progress: Any
    phase_action: Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
    on_failure: Callable[[Path, dict[str, Any], str, str, str], None]
    finalize_report: Callable[..., bool]
    finalize_without: Callable[..., None]


def build_advance_context(
    request: AdvanceStepRequest,
    *,
    progress: Any,
    run_phase_action_default: Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]],
    record_failure_default: Callable[[Path, dict[str, Any], str, str, str], None],
    finalize_report_default: Callable[..., bool],
    finalize_without_default: Callable[..., None],
    run_repository_factory: Callable[[Path], RunRepository] = RunRepository,
) -> AdvanceContext:
    run_dir = request.run_dir
    config = request.config
    to_stage = request.to_stage
    repo = request.repository or run_repository_factory(run_dir)
    state = repo.load_state()
    plan = repo.get_plan()
    return AdvanceContext(
        run_dir=run_dir,
        config=config,
        to_stage=to_stage,
        validator=request.validator,
        repo=repo,
        state=state,
        plan=plan,
        db_reachable=bool(config.get("validate", {}).get("db_reachable", False)),
        progress=progress,
        phase_action=request.run_phase_action_fn or run_phase_action_default,
        on_failure=request.record_failure_fn or record_failure_default,
        finalize_report=request.finalize_report_if_enabled_fn or finalize_report_default,
        finalize_without=request.finalize_without_report_fn or finalize_without_default,
    )


def run_advance_pipeline(
    ctx: AdvanceContext,
    *,
    pre_index_handlers: tuple[Callable[[AdvanceContext], dict[str, Any] | None], ...],
    indexed_handlers: tuple[Callable[[AdvanceContext, LoadedStageIndex], dict[str, Any] | None], ...],
    report_handler: Callable[[AdvanceContext], dict[str, Any] | None],
    load_index_fn: Callable[[Path], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    complete_phase_result_fn: Callable[[AdvanceContext, str], dict[str, Any]],
) -> dict[str, Any]:
    for handler in pre_index_handlers:
        result = handler(ctx)
        if result is not None:
            return result

    units, proposals, acceptance = load_index_fn(ctx.run_dir)
    index = LoadedStageIndex(units=units, proposals=proposals, acceptance=acceptance)
    for handler in indexed_handlers:
        result = handler(ctx, index)
        if result is not None:
            return result

    report_result = report_handler(ctx)
    if report_result is not None:
        return report_result

    return complete_phase_result_fn(ctx, ctx.state["current_phase"])
