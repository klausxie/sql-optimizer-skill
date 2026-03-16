from __future__ import annotations

from typing import Any, Callable

from ..errors import StageError
from ..io_utils import write_json, write_jsonl
from ..run_paths import canonical_paths
from .run_selection import filter_units_by_sql_keys, finalize_selection_summary


def _selection_examples(units: list[dict[str, Any]], *, limit: int = 5) -> str:
    examples = [
        str(row.get("sqlKey") or "").strip()
        for row in units
        if str(row.get("sqlKey") or "").strip()
    ]
    return ", ".join(examples[:limit])


def advance_diagnose(
    ctx: Any,
    *,
    phase_transitions: dict[str, str | None],
    mark_updated: Callable[[dict[str, Any]], None],
    complete_phase_result: Callable[[Any, str], dict[str, Any]],
    finalize_completed_run: Callable[[Any], None],
    handle_phase_failure: Callable[[Any, str, StageError], None],
    diagnose_execute: Callable[[dict[str, Any], Any, Any], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    """Advance the diagnose phase.

    This handler:
    1. Executes the diagnose stage (scan + optional baseline)
    2. Filters SQL units by selection criteria
    3. Updates the run plan with selected SQL keys
    4. Transitions to the optimize phase

    Args:
        ctx: Advance context with run_dir, config, state, etc.
        phase_transitions: Map of phase to next phase
        mark_updated: Function to mark state as updated
        complete_phase_result: Function to create completion result
        finalize_completed_run: Function to finalize run
        handle_phase_failure: Function to handle phase failures
        diagnose_execute: Function to execute diagnose stage

    Returns:
        Completion result or None if phase already done
    """
    paths = canonical_paths(ctx.run_dir)

    # Check if diagnose phase already completed
    if ctx.state["phase_status"]["diagnose"] == "DONE":
        return None

    ctx.progress.report_phase_start("diagnose", "Diagnosing MyBatis mapper files")

    try:
        units, attempts = ctx.phase_action(
            ctx.config,
            "diagnose",
            lambda: diagnose_execute(ctx.config, ctx.run_dir, ctx.validator),
        )
        ctx.state["attempts_by_phase"]["diagnose"] += attempts
    except StageError as exc:
        handle_phase_failure(ctx, "diagnose", exc)
        raise

    scanned_units = list(units)
    selection = (
        dict(ctx.plan.get("selection") or {})
        if isinstance(ctx.plan.get("selection"), dict)
        else None
    )

    # Filter by SQL key selection
    selected_units, missing_sql_keys, ambiguous_sql_keys = filter_units_by_sql_keys(
        scanned_units, (selection or {}).get("sql_keys")
    )

    if ambiguous_sql_keys:
        details = []
        for requested, matches in ambiguous_sql_keys.items():
            details.append(f"{requested} -> {', '.join(matches[:5])}")
        exc = StageError(
            "diagnose selection matched multiple sql keys; use a more specific key. "
            + "; ".join(details),
            reason_code="DIAGNOSE_SELECTION_SQL_KEY_AMBIGUOUS",
        )
        handle_phase_failure(ctx, "diagnose", exc)
        raise exc

    if missing_sql_keys:
        examples = _selection_examples(scanned_units)
        exc = StageError(
            "diagnose selection did not match sql keys: "
            + ", ".join(missing_sql_keys)
            + ". Accepted forms: full sqlKey, namespace.statementId, statementId, or statementId#vN."
            + (f" Available sqlKeys: {examples}" if examples else ""),
            reason_code="DIAGNOSE_SELECTION_SQL_KEY_NOT_FOUND",
        )
        handle_phase_failure(ctx, "diagnose", exc)
        raise exc

    # Handle selection artifacts
    artifact_refs = [str(paths.scan_units_path)]
    if selection:
        selection = finalize_selection_summary(
            selection, scanned_units=scanned_units, selected_units=selected_units
        )
        ctx.plan["selection"] = selection
        selection_path = paths.scan_dir / "selection.json"
        write_json(selection_path, selection)
        write_jsonl(paths.scan_units_path, selected_units)
        artifact_refs.append(str(selection_path))

    units = selected_units
    ctx.plan["sql_keys"] = [u["sqlKey"] for u in units]
    ctx.repo.set_plan(ctx.plan)

    # Update phase status
    ctx.state["phase_status"]["diagnose"] = "DONE"
    ctx.state["current_phase"] = str(phase_transitions["diagnose"])
    ctx.state["statements"] = {
        k: {"optimize": "PENDING", "validate": "PENDING", "apply": "PENDING"}
        for k in ctx.plan["sql_keys"]
    }

    mark_updated(ctx.state)
    ctx.repo.save_state(ctx.state)

    ctx.repo.append_step_result(
        "diagnose",
        "DONE",
        artifact_refs=artifact_refs,
        detail={
            "sql_keys": ctx.plan["sql_keys"],
            "selection": ctx.plan.get("selection"),
        },
    )

    ctx.progress.report_phase_complete("diagnose")

    if selection:
        ctx.progress.report_info(
            f"Found {len(units)} SQL statements to analyze (selected {selection.get('selected_count', len(units))} of {selection.get('scanned_count', len(scanned_units))})"
        )
    else:
        ctx.progress.report_info(f"Found {len(units)} SQL statements to analyze")

    # Finalize if diagnose is the target stage
    if ctx.to_stage == "diagnose":
        finalize_completed_run(ctx)

    return complete_phase_result(ctx, "diagnose")
