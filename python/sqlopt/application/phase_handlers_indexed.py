from __future__ import annotations

from typing import Any, Callable

from ..errors import StageError
from ..run_paths import canonical_paths


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
    if ctx.to_stage not in statement_phase_targets[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(phase_transitions[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_phase_event(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["validate"] = "SKIPPED"
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            finalize_completed_run(ctx)
        return complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("optimize", "Generating optimization proposals")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            phase,
            lambda: optimize_execute_one(index.units[key], ctx.run_dir, ctx.validator),
        )
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_phase_event(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(paths.proposals_path)],
    )
    return {"complete": False, "phase": phase, "sql_key": key}


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
    if ctx.to_stage not in statement_phase_targets[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(phase_transitions[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_phase_event(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        if ctx.to_stage == phase:
            ctx.state["phase_status"]["patch_generate"] = "SKIPPED"
            ctx.repo.save_state(ctx.state)
            finalize_completed_run(ctx)
        return complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("validate", "Validating optimized SQL candidates")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            phase,
            lambda: validate_execute_one(
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
        handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_phase_event(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(paths.acceptance_path)],
    )
    return {"complete": False, "phase": phase, "sql_key": key}


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
    if ctx.to_stage not in statement_phase_targets[phase] or ctx.state["phase_status"][phase] == "DONE":
        return None
    key = next_pending_sql(ctx.state, phase)
    if key is None:
        ctx.state["phase_status"][phase] = "DONE"
        ctx.state["current_phase"] = str(phase_transitions[phase])
        ctx.repo.save_state(ctx.state)
        ctx.repo.append_phase_event(phase, "DONE")
        ctx.progress.report_phase_complete(phase)
        ctx.repo.set_run_status("READY_TO_FINALIZE")
        if ctx.to_stage == phase:
            finalize_completed_run(ctx)
        return complete_phase_result(ctx, phase)

    total_statements = len(ctx.plan["sql_keys"])
    completed = sum(1 for v in ctx.state["statements"].values() if v.get(phase) == "DONE")
    if int(ctx.state["attempts_by_phase"].get(phase, 0)) == 0:
        ctx.progress.report_phase_start("patch_generate", "Generating patch files")
    ctx.progress.report_statement_progress(completed + 1, total_statements, key)

    try:
        _, attempts = ctx.phase_action(
            ctx.config,
            phase,
            lambda: patch_execute_one(
                index.units[key],
                index.acceptance.get(key, {"status": "NEED_MORE_PARAMS"}),
                ctx.run_dir,
                ctx.validator,
                config=ctx.config,
            ),
        )
        ctx.state["attempts_by_phase"][phase] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, phase, exc)
        raise
    ctx.state["statements"][key][phase] = "DONE"
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_phase_event(
        phase,
        "DONE",
        sql_key=key,
        artifact_refs=[str(paths.patches_path)],
    )
    return {"complete": False, "phase": phase, "sql_key": key}
