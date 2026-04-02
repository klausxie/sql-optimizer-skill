from __future__ import annotations

from ..run_paths import REL_ARTIFACTS_ACCEPTANCE, REL_ARTIFACTS_PATCHES, REL_ARTIFACTS_PROPOSALS, REL_REPORT_JSON, REL_SQL_CATALOG


def render_summary_md(run_id: str, verdict: str, readiness: str, stats: dict, phase_status: dict[str, str]) -> str:
    del readiness
    lines = [
        f"# SQL Optimization Summary: {run_id}",
        "",
        f"- verdict: `{verdict}`",
        f"- sql units: `{stats.get('sql_units', 0)}`",
        f"- accepted: `{stats.get('acceptance_pass', 0)}`",
        f"- blocked: `{stats.get('blocked_sql_count', 0)}`",
        f"- patch applicable: `{stats.get('patch_applicable_count', 0)}`",
        f"- phases: `{phase_status}`",
        "",
    ]
    return "\n".join(lines)


def render_report_md(
    run_id: str,
    verdict: str,
    readiness: str,
    stats: dict,
    phase_status: dict[str, str],
    attempts_by_phase: dict[str, int],
    next_actions: list[dict],
    top_blockers: list[dict],
    sql_rows: list[dict],
    proposal_rows: list[dict],
) -> str:
    del readiness, attempts_by_phase, sql_rows, proposal_rows
    lines = [
        f"# SQL Optimization Report: {run_id}",
        "",
        f"- verdict: `{verdict}`",
        f"- sql units: `{stats.get('sql_units', 0)}`",
        f"- accepted: `{stats.get('acceptance_pass', 0)}`",
        f"- blocked: `{stats.get('blocked_sql_count', 0)}`",
        f"- patch applicable: `{stats.get('patch_applicable_count', 0)}`",
        f"- phases: `{phase_status}`",
        "",
        "## Next Actions",
    ]
    if next_actions:
        for action in next_actions:
            lines.append(f"- `{action.get('action_id')}`: {action.get('reason')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Top Blockers"])
    if top_blockers:
        for row in top_blockers:
            lines.append(f"- `{row.get('code')}`: `{row.get('count')}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- report: `{run_id}/{REL_REPORT_JSON}`",
            f"- proposals: `{run_id}/{REL_ARTIFACTS_PROPOSALS}`",
            f"- acceptance: `{run_id}/{REL_ARTIFACTS_ACCEPTANCE}`",
            f"- patches: `{run_id}/{REL_ARTIFACTS_PATCHES}`",
            f"- sql catalog: `{run_id}/{REL_SQL_CATALOG}`",
            "",
        ]
    )
    return "\n".join(lines)
