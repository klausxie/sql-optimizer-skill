from __future__ import annotations

from typing import Any, Callable

from ..errors import StageError


def advance_report(
    ctx: Any,
    *,
    resolve_report_resume_decision: Callable[[dict[str, Any], str, dict[str, Any]], Any],
    report_enabled: Callable[[dict[str, Any]], bool],
    report_phase_complete_for_result: Callable[[dict[str, Any], str, dict[str, Any]], bool],
) -> dict[str, Any] | None:
    report_resume = resolve_report_resume_decision(ctx.state, ctx.to_stage, ctx.config)
    if report_resume is None:
        return None
    if report_enabled(ctx.config):
        report_ok = ctx.finalize_report(ctx.run_dir, ctx.config, ctx.validator, ctx.state, final_meta_status=report_resume.final_meta_status)
        if ctx.to_stage == "report" and not report_ok:
            raise StageError(
                "report finalization failed",
                reason_code=ctx.state.get("last_reason_code") or "RUNTIME_RETRY_EXHAUSTED",
            )
    else:
        ctx.finalize_without(ctx.run_dir, ctx.state, final_meta_status=report_resume.final_meta_status)
    return {"complete": report_phase_complete_for_result(ctx.state, ctx.to_stage, ctx.config), "phase": report_resume.phase}
