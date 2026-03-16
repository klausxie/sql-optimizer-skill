from __future__ import annotations

from typing import Any, Callable

from ..errors import StageError
from ..run_paths import canonical_paths


def _complete_statement_phase(
    ctx: Any,
    *,
    phase: str,
    next_phase: str | None,
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    after_complete: Callable[[], None] | None = None,
) -> dict[str, Any]:
    ctx.state["phase_status"][phase] = "DONE"
    ctx.state["current_phase"] = str(next_phase)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(phase, "DONE")
    ctx.progress.report_phase_complete(phase)
    if after_complete is not None:
        after_complete()
    return complete_phase_result(ctx, phase)


def _advance_statement_phase(
    ctx: Any,
    index: Any,
    *,
    phase: str,
    artifact_ref: str,
    phase_start_message: str,
    execute_for_key: Callable[[str], Any],
    phase_transitions: dict[str, str | None],
    statement_phase_targets: dict[str, set[str]],
    next_pending_sql: Callable[[dict[str, Any], str], str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    after_complete: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    if ctx.to_stage not in statement_phase_targets[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None

    key = next_pending_sql(ctx.state, phase)
    if key is None:
        return _complete_statement_phase(
            ctx,
            phase=phase,
            next_phase=phase_transitions[phase],
            complete_phase_result=complete_phase_result,
            finalize_completed_run=finalize_completed_run,
            after_complete=after_complete,
        )

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start(phase, phase_start_message)
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(ctx.config, phase, lambda: execute_for_key(key))
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, phase, exc)
        raise

    ctx.state["statements"][key][phase] = "DONE"
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(phase, "DONE", sql_key=key, artifact_refs=[artifact_ref])
    return {"complete": False, "phase": phase, "sql_key": key}


def advance_optimize(
    ctx: Any,
    index: Any,
    *,
    phase_transitions: dict[str, str | None],
    statement_phase_targets: dict[str, set[str]],
    next_pending_sql: Callable[[dict[str, Any], str], str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    optimize_execute_one: Callable[[dict[str, Any], Any, Any], dict[str, Any]],
) -> dict[str, Any] | None:
    paths = canonical_paths(ctx.run_dir)
    phase = "optimize"

    def _after_complete() -> None:
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["validate"] = "SKIPPED"
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            finalize_completed_run(ctx)

    return _advance_statement_phase(
        ctx,
        index,
        phase=phase,
        artifact_ref=str(paths.proposals_path),
        phase_start_message="Generating optimization proposals",
        execute_for_key=lambda key: optimize_execute_one(index.units[key], ctx.run_dir, ctx.validator),
        phase_transitions=phase_transitions,
        statement_phase_targets=statement_phase_targets,
        next_pending_sql=next_pending_sql,
        mark_updated=mark_updated,
        complete_phase_result=complete_phase_result,
        finalize_completed_run=finalize_completed_run,
        handle_phase_failure=handle_phase_failure,
        after_complete=_after_complete,
    )


def advance_validate(
    ctx: Any,
    index: Any,
    *,
    phase_transitions: dict[str, str | None],
    statement_phase_targets: dict[str, set[str]],
    next_pending_sql: Callable[[dict[str, Any], str], str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    validate_execute_one: Callable[..., dict[str, Any]],
) -> dict[str, Any] | None:
    paths = canonical_paths(ctx.run_dir)
    phase = "validate"

    def _after_complete() -> None:
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            finalize_completed_run(ctx)

    return _advance_statement_phase(
        ctx,
        index,
        phase=phase,
        artifact_ref=str(paths.acceptance_path),
        phase_start_message="Validating optimized SQL candidates",
        execute_for_key=lambda key: validate_execute_one(
            index.units[key],
            index.proposals.get(key, {}),
            ctx.run_dir,
            ctx.validator,
            db_reachable=ctx.db_reachable,
            config=ctx.config,
        ),
        phase_transitions=phase_transitions,
        statement_phase_targets=statement_phase_targets,
        next_pending_sql=next_pending_sql,
        mark_updated=mark_updated,
        complete_phase_result=complete_phase_result,
        finalize_completed_run=finalize_completed_run,
        handle_phase_failure=handle_phase_failure,
        after_complete=_after_complete,
    )


def advance_patch_generate(
    ctx: Any,
    index: Any,
    *,
    phase_transitions: dict[str, str | None],
    statement_phase_targets: dict[str, set[str]],
    next_pending_sql: Callable[[dict[str, Any], str], str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    patch_execute_one: Callable[..., dict[str, Any]],
) -> dict[str, Any] | None:
    paths = canonical_paths(ctx.run_dir)
    phase = "patch_generate"

    def _after_complete() -> None:
        ctx.repo.set_meta_status("READY_TO_FINALIZE")
        if ctx.to_stage == phase:
            finalize_completed_run(ctx)

    return _advance_statement_phase(
        ctx,
        index,
        phase=phase,
        artifact_ref=str(paths.patches_path),
        phase_start_message="Generating patch files",
        execute_for_key=lambda key: patch_execute_one(
            index.units[key],
            index.acceptance.get(key, {"status": "NEED_MORE_PARAMS"}),
            ctx.run_dir,
            ctx.validator,
            config=ctx.config,
        ),
        phase_transitions=phase_transitions,
        statement_phase_targets=statement_phase_targets,
        next_pending_sql=next_pending_sql,
        mark_updated=mark_updated,
        complete_phase_result=complete_phase_result,
        finalize_completed_run=finalize_completed_run,
        handle_phase_failure=handle_phase_failure,
        after_complete=_after_complete,
    )
