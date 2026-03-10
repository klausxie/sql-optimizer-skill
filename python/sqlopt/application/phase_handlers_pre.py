from __future__ import annotations

from typing import Any, Callable

from ..errors import StageError
from ..run_paths import canonical_paths


def advance_preflight(
    ctx: Any,
    *,
    phase_transitions: dict[str, str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    preflight_execute: Callable[[dict[str, Any], Any], object],
) -> dict[str, Any] | None:
    paths = canonical_paths(ctx.run_dir)
    if ctx.state["phase_status"]["preflight"] == "DONE":
        return None
    ctx.progress.report_phase_start("preflight", "Checking configuration and environment")
    try:
        _, attempts = ctx.phase_action(ctx.config, "preflight", lambda: preflight_execute(ctx.config, ctx.run_dir))
        ctx.state["attempts_by_phase"]["preflight"] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, "preflight", exc)
        raise
    ctx.state["phase_status"]["preflight"] = "DONE"
    ctx.state["current_phase"] = str(phase_transitions["preflight"])
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        "preflight",
        "DONE",
        artifact_refs=[str(paths.preflight_path)],
    )
    ctx.progress.report_phase_complete("preflight")
    if ctx.to_stage == "preflight":
        finalize_completed_run(ctx)
    return complete_phase_result(ctx, "preflight")


def advance_scan(
    ctx: Any,
    *,
    phase_transitions: dict[str, str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    scan_execute: Callable[[dict[str, Any], Any, Any], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    paths = canonical_paths(ctx.run_dir)
    if ctx.state["phase_status"]["scan"] == "DONE":
        return None
    ctx.progress.report_phase_start("scan", "Scanning MyBatis mapper files")
    try:
        units, attempts = ctx.phase_action(ctx.config, "scan", lambda: scan_execute(ctx.config, ctx.run_dir, ctx.validator))
        ctx.state["attempts_by_phase"]["scan"] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, "scan", exc)
        raise
    ctx.plan["sql_keys"] = [u["sqlKey"] for u in units]
    ctx.repo.set_plan(ctx.plan)
    ctx.state["phase_status"]["scan"] = "DONE"
    ctx.state["current_phase"] = str(phase_transitions["scan"])
    ctx.state["statements"] = {
        k: {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"} for k in ctx.plan["sql_keys"]
    }
    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)
    ctx.repo.append_step_result(
        "scan",
        "DONE",
        artifact_refs=[str(paths.scan_units_path)],
        detail={"sql_keys": ctx.plan["sql_keys"]},
    )
    ctx.progress.report_phase_complete("scan")
    ctx.progress.report_info(f"Found {len(units)} SQL statements to analyze")
    if ctx.to_stage == "scan":
        finalize_completed_run(ctx)
    return complete_phase_result(ctx, "scan")
