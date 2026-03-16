from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from ..errors import StageError
from . import phase_handlers


@dataclass(frozen=True)
class HandlerRegistry:
    complete_phase_result: Callable[[Any, str], dict[str, Any]]
    advance_diagnose: Callable[[Any], dict[str, Any] | None]
    advance_scan: Callable[[Any], dict[str, Any] | None]
    advance_optimize: Callable[[Any, Any], dict[str, Any] | None]
    advance_validate: Callable[[Any, Any], dict[str, Any] | None]
    advance_patch_generate: Callable[[Any, Any], dict[str, Any] | None]
    advance_report: Callable[[Any], dict[str, Any] | None]
    pre_index_handlers: tuple[Callable[[Any], dict[str, Any] | None], ...]
    indexed_handlers: tuple[Callable[[Any, Any], dict[str, Any] | None], ...]
    report_handler: Callable[[Any], dict[str, Any] | None]


def build_handler_registry(
    *,
    phase_transitions: dict[str, str | None],
    statement_phase_targets: dict[str, set[str]],
    next_pending_sql: Callable[[dict[str, Any], str], str | None],
    report_enabled: Callable[[dict[str, Any]], bool],
    is_complete_to_stage: Callable[[dict[str, Any], str, bool], bool],
    resolve_report_resume_decision: Callable[
        [dict[str, Any], str, dict[str, Any]], Any
    ],
    report_phase_complete_for_result: Callable[
        [dict[str, Any], str, dict[str, Any]], bool
    ],
    diagnose_execute: Callable[[dict[str, Any], Any, Any], list[dict[str, Any]]],
    scan_execute: Callable[[dict[str, Any], Any, Any], list[dict[str, Any]]],
    optimize_execute_one: Callable[..., dict[str, Any]],
    validate_execute_one: Callable[..., dict[str, Any]],
    patch_execute_one: Callable[..., dict[str, Any]],
) -> HandlerRegistry:
    def _mark_updated(state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

    def _complete_phase_result(ctx: Any, phase: str) -> dict[str, Any]:
        return {
            "complete": is_complete_to_stage(
                ctx.state, ctx.to_stage, report_enabled(ctx.config)
            ),
            "phase": phase,
        }

    def _finalize_completed_run(ctx: Any) -> None:
        if report_enabled(ctx.config):
            ctx.finalize_report(
                ctx.run_dir,
                ctx.config,
                ctx.validator,
                ctx.state,
                final_meta_status="COMPLETED",
            )
        else:
            ctx.finalize_without(ctx.run_dir, ctx.state, final_meta_status="COMPLETED")

    def _handle_phase_failure(ctx: Any, phase: str, exc: StageError) -> None:
        ctx.on_failure(
            ctx.run_dir,
            ctx.state,
            phase,
            exc.reason_code or "RUNTIME_RETRY_EXHAUSTED",
            str(exc),
        )
        if report_enabled(ctx.config):
            ctx.finalize_report(
                ctx.run_dir,
                ctx.config,
                ctx.validator,
                ctx.state,
                final_meta_status="FAILED",
            )
        else:
            ctx.repo.set_meta_status("FAILED")

    def _advance_diagnose(ctx: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_diagnose(
            ctx,
            phase_transitions=phase_transitions,
            mark_updated=_mark_updated,
            complete_phase_result=_complete_phase_result,
            finalize_completed_run=_finalize_completed_run,
            handle_phase_failure=_handle_phase_failure,
            diagnose_execute=diagnose_execute,
        )

    def _advance_scan(ctx: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_scan(
            ctx,
            phase_transitions=phase_transitions,
            mark_updated=_mark_updated,
            complete_phase_result=_complete_phase_result,
            finalize_completed_run=_finalize_completed_run,
            handle_phase_failure=_handle_phase_failure,
            scan_execute=scan_execute,
        )

    def _advance_optimize(ctx: Any, index: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_optimize(
            ctx,
            index,
            phase_transitions=phase_transitions,
            statement_phase_targets=statement_phase_targets,
            next_pending_sql=next_pending_sql,
            mark_updated=_mark_updated,
            complete_phase_result=_complete_phase_result,
            finalize_completed_run=_finalize_completed_run,
            handle_phase_failure=_handle_phase_failure,
            optimize_execute_one=lambda sql_unit, run_dir, validator: (
                optimize_execute_one(sql_unit, run_dir, validator, config=ctx.config)
            ),
        )

    def _advance_validate(ctx: Any, index: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_validate(
            ctx,
            index,
            phase_transitions=phase_transitions,
            statement_phase_targets=statement_phase_targets,
            next_pending_sql=next_pending_sql,
            mark_updated=_mark_updated,
            complete_phase_result=_complete_phase_result,
            finalize_completed_run=_finalize_completed_run,
            handle_phase_failure=_handle_phase_failure,
            validate_execute_one=validate_execute_one,
        )

    def _advance_patch_generate(ctx: Any, index: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_patch_generate(
            ctx,
            index,
            phase_transitions=phase_transitions,
            statement_phase_targets=statement_phase_targets,
            next_pending_sql=next_pending_sql,
            mark_updated=_mark_updated,
            complete_phase_result=_complete_phase_result,
            finalize_completed_run=_finalize_completed_run,
            handle_phase_failure=_handle_phase_failure,
            patch_execute_one=patch_execute_one,
        )

    def _advance_report(ctx: Any) -> dict[str, Any] | None:
        return phase_handlers.advance_report(
            ctx,
            resolve_report_resume_decision=resolve_report_resume_decision,
            report_enabled=report_enabled,
            report_phase_complete_for_result=report_phase_complete_for_result,
        )

    pre_index_handlers = (_advance_diagnose,)
    indexed_handlers = (_advance_optimize, _advance_validate, _advance_patch_generate)
    return HandlerRegistry(
        complete_phase_result=_complete_phase_result,
        advance_diagnose=_advance_diagnose,
        advance_scan=_advance_scan,
        advance_optimize=_advance_optimize,
        advance_validate=_advance_validate,
        advance_patch_generate=_advance_patch_generate,
        advance_report=_advance_report,
        pre_index_handlers=pre_index_handlers,
        indexed_handlers=indexed_handlers,
        report_handler=_advance_report,
    )
