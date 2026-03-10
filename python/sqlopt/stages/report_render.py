from __future__ import annotations

from ..run_paths import (
    REL_DIAGNOSTICS_BLOCKERS_SUMMARY,
    REL_DIAGNOSTICS_SQL_ARTIFACTS,
    REL_DIAGNOSTICS_SQL_OUTCOMES,
    REL_OVERVIEW_REPORT_JSON,
    REL_OVERVIEW_REPORT_MD,
    REL_PIPELINE_MANIFEST,
    REL_PIPELINE_OPTIMIZE_PROPOSALS,
    REL_PIPELINE_PATCH_RESULTS,
    REL_PIPELINE_SCAN_FRAGMENTS,
    REL_PIPELINE_SCAN_UNITS,
    REL_PIPELINE_VALIDATE_ACCEPTANCE,
    REL_PIPELINE_VERIFICATION_LEDGER,
    REL_PIPELINE_OPS_FAILURES,
    REL_RUN_INDEX_JSON,
    REL_SQL_CATALOG,
)


def render_summary_md(run_id: str, verdict: str, readiness: str, stats: dict, phase_status: dict[str, str]) -> str:
    verification = stats.get("verification") or {}
    top_actionable = (stats.get("top_actionable_sql") or [])[:3]
    validation_warnings = stats.get("validation_warnings") or []
    semantic_gate_pass = stats.get("semantic_gate_pass_count", 0)
    semantic_gate_fail = stats.get("semantic_gate_fail_count", 0)
    semantic_gate_uncertain = stats.get("semantic_gate_uncertain_count", 0)
    confidence_upgraded_count = stats.get("confidence_upgraded_count", 0)
    confidence_upgrade_rate = stats.get("confidence_upgrade_rate", 0)
    confidence_upgrade_by_source = stats.get("confidence_upgrade_by_evidence_source", {})
    lines = [
        f"# SQL 优化总结：{run_id}",
        "",
        f"- 优化结论：`{verdict}`",
        f"- 发布就绪度：`{readiness}`",
        f"- 证据置信度：`{stats.get('evidence_confidence', 'unknown')}`",
        f"- SQL 单元数：`{stats.get('sql_units', 0)}`",
        f"- 验证结果：通过 `{stats.get('acceptance_pass', 0)}`, 失败 `{stats.get('acceptance_fail', 0)}`, 需更多参数 `{stats.get('acceptance_need_more_params', 0)}`",
        f"- 交付物：补丁 `{stats.get('patch_files', 0)}`, 可应用 `{stats.get('patch_applicable_count', 0)}`",
        f"- 失败统计：致命 `{stats.get('fatal_count', 0)}`, 可重试 `{stats.get('retryable_count', 0)}`, 可降级 `{stats.get('degradable_count', 0)}`",
        f"- 验证状态：已验证 `{verification.get('verified_count', 0)}`, 部分 `{verification.get('partial_count', 0)}`, 未验证 `{verification.get('unverified_count', 0)}`",
        f"- 语义门：PASS `{semantic_gate_pass}`, FAIL `{semantic_gate_fail}`, UNCERTAIN `{semantic_gate_uncertain}`",
        f"- 置信度升级：`{confidence_upgraded_count}` (`{confidence_upgrade_rate}`), 来源 `{confidence_upgrade_by_source}`",
        "",
        "## 优先处理的 SQL",
    ]
    if top_actionable:
        for row in top_actionable:
            delivery = row.get("delivery_status") or row.get("delivery_tier")
            lines.append(
                f"- {row.get('sql_key')}: {row.get('why_now') or row.get('summary')} ({row.get('priority')}, {delivery})"
            )
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
        ]
    )
    if validation_warnings:
        lines.extend(["## 警告"])
        for warning in validation_warnings[:3]:
            lines.append(f"- {warning}")
        lines.append("")
    lines.extend(
        [
            f"- 阶段状态：preflight `{phase_status.get('preflight', 'PENDING')}`, scan `{phase_status.get('scan', 'PENDING')}`, optimize `{phase_status.get('optimize', 'PENDING')}`, validate `{phase_status.get('validate', 'PENDING')}`, patch_generate `{phase_status.get('patch_generate', 'PENDING')}`, report `{phase_status.get('report', 'DONE')}`",
            "",
        ]
    )
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
    verification = stats.get("verification") or {}
    top_actionable = stats.get("top_actionable_sql") or []
    lines = [
        f"# SQL 优化报告：{run_id}",
        "",
        "## 执行决策",
        f"- 发布就绪度：`{readiness}`",
        f"- 优化结论：`{verdict}`",
        f"- 证据置信度：`{stats.get('evidence_confidence', 'unknown')}`",
        f"- 范围：SQL 单元 `{stats.get('sql_units', 0)}`, 优化建议 `{stats.get('proposals', 0)}`",
        f"- 交付快照：补丁 `{stats.get('patch_files', 0)}`, 可应用 `{stats.get('patch_applicable_count', 0)}`, 阻塞 SQL `{stats.get('blocked_sql_count', 0)}`",
        f"- 性能证据：改进 `{stats.get('perf_improved_count', 0)}`, 未改进 `{stats.get('perf_compared_but_not_improved_count', 0)}`",
        f"- 验证状态：已验证 `{verification.get('verified_count', 0)}`, 部分 `{verification.get('partial_count', 0)}`, 未验证 `{verification.get('unverified_count', 0)}`",
        f"- 语义门：PASS `{stats.get('semantic_gate_pass_count', 0)}`, FAIL `{stats.get('semantic_gate_fail_count', 0)}`, UNCERTAIN `{stats.get('semantic_gate_uncertain_count', 0)}`",
        f"- 置信度升级：`{stats.get('confidence_upgraded_count', 0)}` (`{stats.get('confidence_upgrade_rate', 0)}`), 来源 `{stats.get('confidence_upgrade_by_evidence_source', {})}`",
        f"- 物化模式：`{stats.get('materialization_mode_counts', {})}`",
        f"- 物化原因：`{stats.get('materialization_reason_counts', {})}`",
        f"- 物化操作：`{stats.get('materialization_reason_group_counts', {})}`",
        "",
        "## 优先处理的 SQL",
    ]
    if top_actionable:
        lines.extend(
            [
                "| SQL 键 | 优先级 | 可操作性 | 交付状态 | 主阻断 | 补丁可应用 | 当前原因 | 摘要 |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in top_actionable:
            patch_label = "true" if row.get("patch_applicable") is True else ("false" if row.get("patch_applicable") is False else "n/a")
            delivery = row.get("delivery_status") or row.get("delivery_tier")
            lines.append(
                f"| `{row.get('sql_key')}` | `{row.get('priority')}` | `{row.get('actionability_tier')}` | `{delivery}` | `{row.get('blocker_primary_code') or 'n/a'}` | `{patch_label}` | {row.get('why_now') or 'n/a'} | {row.get('summary')} |"
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 主要风险",
        ]
    )
    if top_blockers:
        for blocker in top_blockers:
            lines.append(
                f"- `{blocker.get('code')}` (`{blocker.get('severity')}`): 数量 `{blocker.get('count')}`, 影响 SQL `{len(blocker.get('sql_keys') or [])}`"
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 交付状态",
            f"- preflight: `{phase_status.get('preflight', 'PENDING')}`",
            f"- scan: `{phase_status.get('scan', 'PENDING')}` (尝试 `{attempts_by_phase.get('scan', 0)}`)",
            f"- optimize: `{phase_status.get('optimize', 'PENDING')}` (尝试 `{attempts_by_phase.get('optimize', 0)}`)",
            f"- validate: `{phase_status.get('validate', 'PENDING')}` (尝试 `{attempts_by_phase.get('validate', 0)}`)",
            f"- patch_generate: `{phase_status.get('patch_generate', 'PENDING')}` (尝试 `{attempts_by_phase.get('patch_generate', 0)}`)",
            f"- report: `{phase_status.get('report', 'DONE')}`",
            "",
            "## 变更组合",
            "| SQL 键 | 状态 | 语义门 | 置信度 | 升级轨迹 | 未升级主因 | 阻断主因 | 来源 | 性能 | 物化 | 补丁可应用 | 补丁决策 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in sql_rows:
        perf_label = "改进" if row.get("perf_improved") is True else ("未改进" if row.get("perf_improved") is False else "未知")
        patch_app = row.get("patch_applicable")
        patch_label = "true" if patch_app is True else ("false" if patch_app is False else "n/a")
        materialization = row.get("rewrite_materialization_mode") or row.get("rewrite_materialization_reason") or "n/a"
        semantic_gate_status = row.get("semantic_gate_status") or "UNKNOWN"
        semantic_confidence = row.get("semantic_gate_confidence") or "UNKNOWN"
        confidence_before_upgrade = row.get("semantic_confidence_before_upgrade")
        semantic_upgrade_reasons = row.get("semantic_upgrade_reasons") or []
        semantic_upgrade_sources = row.get("semantic_upgrade_sources") or []
        semantic_unupgraded_reason = row.get("semantic_unupgraded_reason") or "n/a"
        semantic_blocked_reason = row.get("semantic_blocked_reason") or "n/a"
        if row.get("semantic_confidence_upgraded"):
            upgrade_path = f"{confidence_before_upgrade or 'UNKNOWN'}->{semantic_confidence}"
            upgrade_proof = ",".join(semantic_upgrade_sources) or ",".join(semantic_upgrade_reasons) or "evidence"
            semantic_upgrade_trace = f"{upgrade_path} ({upgrade_proof})"
        else:
            semantic_upgrade_trace = "未升级"
        lines.append(
            f"| `{row.get('sql_key')}` | `{row.get('status')}` | `{semantic_gate_status}` | `{semantic_confidence}` | `{semantic_upgrade_trace}` | `{semantic_unupgraded_reason}` | `{semantic_blocked_reason}` | `{row.get('selected_source')}` | `{perf_label}` | `{materialization}` | `{patch_label}` | `{row.get('patch_selection_code') or 'n/a'}` |"
        )

    lines.extend(["", "## 优化建议分析", "| SQL 键 | 结论 | 问题 | LLM 候选 |", "|---|---|---|---|"])
    if proposal_rows:
        for row in proposal_rows:
            issues = ",".join(row.get("issue_codes") or []) or "无"
            lines.append(
                f"| `{row.get('sql_key')}` | `{row.get('verdict')}` | `{issues}` | `{row.get('llm_candidate_count')}` |"
            )
    else:
        lines.append("| `n/a` | `n/a` | `n/a` | `0` |")

    lines.extend(["", "## 技术证据"])
    pass_count = 0
    for row in sql_rows:
        if str(row.get("status")) != "PASS":
            continue
        pass_count += 1
        refs = row.get("evidence_refs") or []
        lines.append(
            f"- `{row.get('sql_key')}`: 行检查 `{row.get('row_status') or 'n/a'}`, 成本 `{row.get('before_cost')}` -> `{row.get('after_cost')}`"
        )
        if row.get("rewrite_materialization_mode") or row.get("rewrite_materialization_reason"):
            lines.append(
                f"  物化：`{row.get('rewrite_materialization_mode') or 'n/a'}` / `{row.get('rewrite_materialization_reason') or 'n/a'}`"
            )
        lines.append(
            "  语义门："
            f"`{row.get('semantic_gate_status') or 'UNKNOWN'}` / `{row.get('semantic_gate_confidence') or 'UNKNOWN'}`"
            f", 升级 `{row.get('semantic_confidence_upgraded')}`"
            f", 未升级主因 `{row.get('semantic_unupgraded_reason') or 'n/a'}`"
        )
        lines.append(f"  证据：`{refs[0]}`" if refs else "  证据：`n/a`")
    if pass_count == 0:
        lines.append("- 无通过项的技术证据。")

    lines.extend(["", "## 行动计划（未来 24 小时）"])
    if next_actions:
        for action in next_actions:
            cmd = (action.get("commands") or [""])[0]
            title = str(action.get("title") or action.get("action_id") or "action")
            lines.append(f"- {title}: `{cmd}`" if cmd else f"- {title}")
    else:
        lines.append("- 无")

    validation_warnings = stats.get("validation_warnings") or []
    lines.extend(["", "## 验证警告"])
    if validation_warnings:
        for warning in validation_warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 验证覆盖",
            f"- 阶段覆盖：`{verification.get('coverage_by_phase', {})}`",
            f"- 主要差距：`{verification.get('top_reason_codes', [])}`",
            f"- 阻塞 SQL: `{verification.get('blocking_sql_keys', [])}`",
            "",
            "## 附录",
            "",
        ]
    )
    appendix_paths = [
        ("run index", REL_RUN_INDEX_JSON),
        ("overview report", REL_OVERVIEW_REPORT_JSON),
        ("overview markdown", REL_OVERVIEW_REPORT_MD),
        ("pipeline manifest", REL_PIPELINE_MANIFEST),
        ("sql catalog", REL_SQL_CATALOG),
        ("pipeline scan units", REL_PIPELINE_SCAN_UNITS),
        ("pipeline scan fragments", REL_PIPELINE_SCAN_FRAGMENTS),
        ("pipeline proposals", REL_PIPELINE_OPTIMIZE_PROPOSALS),
        ("pipeline acceptance", REL_PIPELINE_VALIDATE_ACCEPTANCE),
        ("pipeline patches", REL_PIPELINE_PATCH_RESULTS),
        ("verification", REL_PIPELINE_VERIFICATION_LEDGER),
        ("failures", REL_PIPELINE_OPS_FAILURES),
        ("sql outcomes", REL_DIAGNOSTICS_SQL_OUTCOMES),
        ("sql artifacts", REL_DIAGNOSTICS_SQL_ARTIFACTS),
        ("blockers summary", REL_DIAGNOSTICS_BLOCKERS_SUMMARY),
    ]
    for label, rel_path in appendix_paths:
        lines.append(f"- {label}: `{run_id}/{rel_path}`")
    lines.append("")
    return "\n".join(lines)
