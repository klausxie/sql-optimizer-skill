from __future__ import annotations


def render_summary_md(run_id: str, verdict: str, readiness: str, stats: dict, phase_status: dict[str, str]) -> str:
    verification = stats.get("verification") or {}
    return "\n".join(
        [
            f"# SQL Optimize Summary: {run_id}",
            "",
            f"- Verdict: `{verdict}`",
            f"- Release Readiness: `{readiness}`",
            f"- Evidence Confidence: `{stats.get('evidence_confidence', 'unknown')}`",
            f"- SQL Units: `{stats.get('sql_units', 0)}`",
            f"- Acceptance: pass `{stats.get('acceptance_pass', 0)}`, fail `{stats.get('acceptance_fail', 0)}`, need params `{stats.get('acceptance_need_more_params', 0)}`",
            f"- Delivery: patches `{stats.get('patch_files', 0)}`, applicable `{stats.get('patch_applicable_count', 0)}`",
            f"- Failures: fatal `{stats.get('fatal_count', 0)}`, retryable `{stats.get('retryable_count', 0)}`, degradable `{stats.get('degradable_count', 0)}`",
            f"- Verification: verified `{verification.get('verified_count', 0)}`, partial `{verification.get('partial_count', 0)}`, unverified `{verification.get('unverified_count', 0)}`",
            f"- Phase Status: preflight `{phase_status.get('preflight', 'PENDING')}`, scan `{phase_status.get('scan', 'PENDING')}`, optimize `{phase_status.get('optimize', 'PENDING')}`, validate `{phase_status.get('validate', 'PENDING')}`, patch_generate `{phase_status.get('patch_generate', 'PENDING')}`, report `{phase_status.get('report', 'DONE')}`",
            "",
        ]
    )


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
    verification = stats.get("verification") or {}
    lines = [
        f"# SQL Optimize Report: {run_id}",
        "",
        "## Executive Decision",
        f"- Release Readiness: `{readiness}`",
        f"- Verdict: `{verdict}`",
        f"- Evidence Confidence: `{stats.get('evidence_confidence', 'unknown')}`",
        f"- Scope: SQL units `{stats.get('sql_units', 0)}`, proposals `{stats.get('proposals', 0)}`",
        f"- Delivery Snapshot: patches `{stats.get('patch_files', 0)}`, applicable `{stats.get('patch_applicable_count', 0)}`, blocked sql `{stats.get('blocked_sql_count', 0)}`",
        f"- Perf Evidence: improved `{stats.get('perf_improved_count', 0)}`, not improved `{stats.get('perf_compared_but_not_improved_count', 0)}`",
        f"- Verification: verified `{verification.get('verified_count', 0)}`, partial `{verification.get('partial_count', 0)}`, unverified `{verification.get('unverified_count', 0)}`",
        f"- Materialization: `{stats.get('materialization_mode_counts', {})}`",
        f"- Materialization Reasons: `{stats.get('materialization_reason_counts', {})}`",
        f"- Materialization Actions: `{stats.get('materialization_reason_group_counts', {})}`",
        "",
        "## Top Risks",
    ]
    if top_blockers:
        for blocker in top_blockers:
            lines.append(
                f"- `{blocker.get('code')}` (`{blocker.get('severity')}`): count `{blocker.get('count')}`, impacted sql `{len(blocker.get('sql_keys') or [])}`"
            )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Delivery Status",
            f"- preflight: `{phase_status.get('preflight', 'PENDING')}`",
            f"- scan: `{phase_status.get('scan', 'PENDING')}` (attempts `{attempts_by_phase.get('scan', 0)}`)",
            f"- optimize: `{phase_status.get('optimize', 'PENDING')}` (attempts `{attempts_by_phase.get('optimize', 0)}`)",
            f"- validate: `{phase_status.get('validate', 'PENDING')}` (attempts `{attempts_by_phase.get('validate', 0)}`)",
            f"- patch_generate: `{phase_status.get('patch_generate', 'PENDING')}` (attempts `{attempts_by_phase.get('patch_generate', 0)}`)",
            f"- report: `{phase_status.get('report', 'DONE')}`",
            "",
            "## Change Portfolio",
            "| SQL Key | Status | Source | Perf | Materialization | Patch Applicable | Patch Decision |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in sql_rows:
        perf_label = "improved" if row.get("perf_improved") is True else ("not-improved" if row.get("perf_improved") is False else "unknown")
        patch_app = row.get("patch_applicable")
        patch_label = "true" if patch_app is True else ("false" if patch_app is False else "n/a")
        materialization = row.get("rewrite_materialization_mode") or row.get("rewrite_materialization_reason") or "n/a"
        lines.append(
            f"| `{row.get('sql_key')}` | `{row.get('status')}` | `{row.get('selected_source')}` | `{perf_label}` | `{materialization}` | `{patch_label}` | `{row.get('patch_selection_code') or 'n/a'}` |"
        )

    lines.extend(["", "## Proposal Insights", "| SQL Key | Verdict | Issues | LLM Candidates |", "|---|---|---|---|"])
    if proposal_rows:
        for row in proposal_rows:
            issues = ",".join(row.get("issue_codes") or []) or "none"
            lines.append(
                f"| `{row.get('sql_key')}` | `{row.get('verdict')}` | `{issues}` | `{row.get('llm_candidate_count')}` |"
            )
    else:
        lines.append("| `n/a` | `n/a` | `n/a` | `0` |")

    lines.extend(["", "## Technical Evidence"])
    pass_count = 0
    for row in sql_rows:
        if str(row.get("status")) != "PASS":
            continue
        pass_count += 1
        refs = row.get("evidence_refs") or []
        lines.append(
            f"- `{row.get('sql_key')}`: row-check `{row.get('row_status') or 'n/a'}`, cost `{row.get('before_cost')}` -> `{row.get('after_cost')}`"
        )
        if row.get("rewrite_materialization_mode") or row.get("rewrite_materialization_reason"):
            lines.append(
                f"  materialization: `{row.get('rewrite_materialization_mode') or 'n/a'}` / `{row.get('rewrite_materialization_reason') or 'n/a'}`"
            )
        lines.append(f"  evidence: `{refs[0]}`" if refs else "  evidence: `n/a`")
    if pass_count == 0:
        lines.append("- No PASS items with technical evidence.")

    lines.extend(["", "## Action Plan (Next 24h)"])
    if next_actions:
        for action in next_actions:
            cmd = (action.get("commands") or [""])[0]
            title = str(action.get("title") or action.get("action_id") or "action")
            lines.append(f"- {title}: `{cmd}`" if cmd else f"- {title}")
    else:
        lines.append("- None")

    validation_warnings = stats.get("validation_warnings") or []
    lines.extend(["", "## Verification Warnings"])
    if validation_warnings:
        for warning in validation_warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Verification Coverage",
            f"- phase coverage: `{verification.get('coverage_by_phase', {})}`",
            f"- top gaps: `{verification.get('top_reason_codes', [])}`",
            f"- blocking sql: `{verification.get('blocking_sql_keys', [])}`",
            "",
            "## Appendix",
            f"- report.json: `{run_id}/report.json`",
            f"- proposals: `{run_id}/proposals/optimization.proposals.jsonl`",
            f"- acceptance: `{run_id}/acceptance/acceptance.results.jsonl`",
            f"- patches: `{run_id}/patches/patch.results.jsonl`",
            f"- verification: `{run_id}/verification/ledger.jsonl`",
            f"- failures: `{run_id}/ops/failures.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)
