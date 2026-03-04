from __future__ import annotations

from typing import Any

from ..failure_classification import classify_reason_code
from ..platforms.sql.materialization_constants import materialization_reason_group
from ..verification.explain import action_reason, assess_sql_outcome


def _append_action_once(actions: list[dict[str, Any]], action: dict[str, Any]) -> None:
    existing = {str(row.get("action_id") or "") for row in actions if isinstance(row, dict)}
    action_id = str(action.get("action_id") or "")
    if action_id and action_id in existing:
        return
    actions.append(action)


def _acceptance_decision_layers(acceptance_row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    decision_layers = dict(acceptance_row.get("decisionLayers") or {})
    return (
        dict(decision_layers.get("evidence") or {}),
        dict(decision_layers.get("delivery") or {}),
        dict(decision_layers.get("acceptance") or {}),
    )


def compute_verdict(stats: dict[str, Any]) -> str:
    if int(stats.get("fatal_count") or 0) > 0:
        return "BLOCKED"
    if int(stats.get("acceptance_fail") or 0) > 0:
        return "ATTENTION"
    if int(stats.get("acceptance_need_more_params") or 0) > 0:
        return "PARTIAL"
    if int(stats.get("sql_units") or 0) == 0:
        return "EMPTY"
    return "PASS"


def compute_release_readiness(verdict: str, stats: dict[str, Any]) -> str:
    if verdict in {"BLOCKED", "ATTENTION"}:
        return "NO_GO"
    if verdict == "PARTIAL":
        return "CONDITIONAL_GO"
    if verdict == "PASS" and int(stats.get("patch_applicable_count") or 0) > 0:
        return "GO"
    return "CONDITIONAL_GO"


def default_next_actions(
    run_id: str,
    verdict: str,
    reason_counts: dict[str, int],
    *,
    top_actionable_sql: list[dict[str, Any]] | None = None,
    verification: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    verification_stats = verification or {}
    top_row = (top_actionable_sql or [None])[0] if top_actionable_sql else None

    if int(verification_stats.get("unverified_pass_count") or 0) > 0 or int(
        verification_stats.get("unverified_applicable_patch_count") or 0
    ) > 0:
        _append_action_once(
            actions,
                {
                    "action_id": "review-evidence",
                    "title": "QA：审查缺失的验证证据",
                    "reason": action_reason("review-evidence"),
                    "applicability": "存在验证门警告",
                    "expected_outcome": "在应用或重构前恢复置信度",
                    "commands": [],
                },
            )

    if isinstance(top_row, dict):
        delivery_tier = str(top_row.get("delivery_tier") or "").strip().upper()
        evidence_state = str(top_row.get("evidence_state") or "").strip().upper()
        evidence_degraded = evidence_state == "DEGRADED" or bool(top_row.get("evidence_degraded"))
        critical_gap = evidence_state == "CRITICAL_GAP"
        acceptance_reason_code = str(top_row.get("acceptance_reason_code") or "").strip().upper()
        hint_title = str(top_row.get("repair_hint_title") or "").strip()
        hint_command = str(top_row.get("repair_hint_command") or "").strip() or None
        if critical_gap:
            _append_action_once(
                actions,
                {
                    "action_id": "review-evidence",
                    "title": "QA：审查缺失的验证证据",
                    "reason": action_reason("review-evidence"),
                    "applicability": "优先处理的 SQL 被标记为 CRITICAL_GAP",
                    "expected_outcome": "在发布或手动干预前恢复置信度",
                    "commands": [],
                },
            )
        elif evidence_degraded and acceptance_reason_code in {"VALIDATE_PARAM_INSUFFICIENT", "VALIDATE_DB_UNREACHABLE"}:
            _append_action_once(
                actions,
                {
                    "action_id": "check-db",
                    "title": "DBA：验证数据库连接",
                    "reason": action_reason("check-db"),
                    "applicability": "决策层表明数据库验证不完整",
                    "expected_outcome": "为最高价值项恢复语义和性能检查",
                    "commands": ['psql "$DSN" -c "select 1;"'],
                },
            )
        if delivery_tier == "PATCHABLE_WITH_REWRITE":
            _append_action_once(
                actions,
                {
                    "action_id": "refactor-mapper",
                    "title": "后端：重构 mapper 以支持模板感知重写",
                    "reason": action_reason("refactor-mapper"),
                    "applicability": "优先处理的 SQL 需要模板感知重写",
                    "expected_outcome": "为最高价值项解锁自动补丁生成",
                    "commands": [hint_command] if hint_command else [],
                },
            )
        elif delivery_tier == "MANUAL_REVIEW":
            _append_action_once(
                actions,
                {
                    "action_id": "resolve-patch-conflict",
                    "title": "后端：手动解决补丁冲突",
                    "reason": action_reason("resolve-patch-conflict"),
                    "applicability": "优先处理的 SQL 处于 MANUAL_REVIEW 状态",
                    "expected_outcome": "在手动冲突解决后应用最高价值补丁",
                    "commands": [hint_command] if hint_command else [],
                },
            )
        elif delivery_tier == "NEEDS_REVIEW":
            _append_action_once(
                actions,
                {
                    "action_id": "review-patchability",
                    "title": "后端：审查补丁可应用性",
                    "reason": action_reason("review-patchability"),
                    "applicability": "优先处理的 SQL 已验证但没有就绪补丁",
                    "expected_outcome": "决定是手动补丁还是调整 mapper 结构",
                    "commands": [],
                },
            )
        elif delivery_tier == "READY_TO_APPLY" and verdict == "PASS":
            _append_action_once(
                actions,
                {
                    "action_id": "apply",
                    "title": "后端：应用生成的补丁",
                    "reason": action_reason("apply"),
                    "applicability": "健康的运行且有可用补丁",
                    "expected_outcome": "应用安全的 SQL 改进",
                    "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id {run_id}"],
                },
            )

    if reason_counts.get("VALIDATE_DB_UNREACHABLE", 0) > 0:
        _append_action_once(
            actions,
            {
                "action_id": "check-db",
                "title": "DBA：验证数据库连接",
                "reason": action_reason("check-db"),
                "applicability": "存在 VALIDATE_DB_UNREACHABLE",
                "expected_outcome": "语义和性能检查可执行",
                "commands": ['psql "$DSN" -c "select 1;"'],
            },
        )
    if reason_counts.get("VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", 0) > 0:
        _append_action_once(
            actions,
            {
                "action_id": "remove-dollar",
                "title": "后端：移除 ${} 动态 SQL",
                "reason": action_reason("remove-dollar"),
                "applicability": "验证中存在安全警告",
                "expected_outcome": "语句变为可补丁",
                "commands": ['rg -n "\\$\\{" src/main/resources/**/*.xml'],
            },
        )
    if verdict in {"BLOCKED", "ATTENTION", "PARTIAL"}:
        _append_action_once(
            actions,
            {
                "action_id": "resume",
                "title": "平台：恢复运行",
                "reason": action_reason("resume"),
                "applicability": "等待中或降级的流水线",
                "expected_outcome": "继续或最终确定处理",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id {run_id}"],
            },
        )
    if not actions:
        _append_action_once(
            actions,
            {
                "action_id": "apply",
                "title": "后端：应用生成的补丁",
                "reason": action_reason("apply"),
                "applicability": "有可用补丁",
                "expected_outcome": "应用安全的 SQL 改进",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id {run_id}"],
            },
        )
    return actions


def build_top_blockers(failures: list[dict[str, Any]], reason_counts: dict[str, int]) -> list[dict[str, Any]]:
    sql_keys_by_code: dict[str, set[str]] = {}
    for row in failures:
        code = str(row.get("reason_code") or "UNKNOWN")
        sql_key = str(row.get("sql_key") or "")
        sql_keys_by_code.setdefault(code, set())
        if sql_key:
            sql_keys_by_code[code].add(sql_key)
    out: list[dict[str, Any]] = []
    for code, count in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]:
        out.append(
            {
                "code": code,
                "count": int(count),
                "ratio": None,
                "severity": classify_reason_code(code, phase="validate"),
                "sql_keys": sorted(sql_keys_by_code.get(code, set())),
            }
        )
    return out


def build_prioritized_sql_keys(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sql: dict[str, dict[str, Any]] = {}
    for row in failures:
        sql_key = str(row.get("sql_key") or "")
        if not sql_key:
            continue
        rcode = str(row.get("reason_code") or "UNKNOWN")
        bucket = by_sql.setdefault(sql_key, {"sql_key": sql_key, "count": 0, "blocker_codes": set(), "has_fatal": False})
        bucket["count"] += 1
        bucket["blocker_codes"].add(rcode)
        if str(row.get("classification") or "") == "fatal":
            bucket["has_fatal"] = True
    rows: list[dict[str, Any]] = []
    for val in by_sql.values():
        rows.append(
            {
                "sql_key": val["sql_key"],
                "priority": "P0" if val["has_fatal"] else "P1",
                "score": int(val["count"]),
                "blocker_codes": sorted(val["blocker_codes"]),
            }
        )
    rows.sort(key=lambda x: (0 if x["priority"] == "P0" else 1, -int(x["score"])))
    return rows[:10]


def build_sql_rows(units: list[dict[str, Any]], acceptance: list[dict[str, Any]], patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    acceptance_by_sql_key = {str(row.get("sqlKey")): row for row in acceptance}
    patch_by_statement = {str(row.get("statementKey")): row for row in patches}
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "")
        statement_key = sql_key.split("#", 1)[0]
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        perf = acceptance_row.get("perfComparison") or {}
        eq = acceptance_row.get("equivalence") or {}
        rows.append(
            {
                "sql_key": sql_key,
                "status": acceptance_row.get("status") or "PENDING",
                "selected_source": acceptance_row.get("selectedCandidateSource") or "n/a",
                "semantic_risk": acceptance_row.get("semanticRisk") or "unknown",
                "perf_improved": perf.get("improved"),
                "before_cost": (perf.get("beforeSummary") or {}).get("totalCost"),
                "after_cost": (perf.get("afterSummary") or {}).get("totalCost"),
                "patch_applicable": patch_row.get("applicable"),
                "patch_selection_code": (patch_row.get("selectionReason") or {}).get("code"),
                "rewrite_materialization_mode": (acceptance_row.get("rewriteMaterialization") or {}).get("mode"),
                "rewrite_materialization_reason": (acceptance_row.get("rewriteMaterialization") or {}).get("reasonCode"),
                "row_status": (eq.get("rowCount") or {}).get("status"),
                "evidence_refs": eq.get("evidenceRefs") or [],
            }
        )
    return rows


def materialization_mode_counts(acceptance: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in acceptance:
        mode = str((row.get("rewriteMaterialization") or {}).get("mode") or "").strip()
        if not mode:
            continue
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def materialization_reason_counts(acceptance: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in acceptance:
        reason = str((row.get("rewriteMaterialization") or {}).get("reasonCode") or "").strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def materialization_reason_group_counts(reason_counts: dict[str, int]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for reason, count in reason_counts.items():
        group = materialization_reason_group(reason)
        if not group:
            continue
        grouped[group] = grouped.get(group, 0) + int(count)
    return grouped


def build_proposal_rows(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        issues = proposal.get("issues") or []
        issue_codes = [str(x.get("code")) for x in issues if isinstance(x, dict) and x.get("code")]
        rows.append(
            {
                "sql_key": str(proposal.get("sqlKey") or ""),
                "verdict": str(proposal.get("verdict") or "UNKNOWN"),
                "issue_codes": issue_codes,
                "llm_candidate_count": len(proposal.get("llmCandidates") or []),
            }
        )
    return rows


def build_top_actionable_sql(
    units: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposal_by_sql_key = {str(row.get("sqlKey") or ""): row for row in proposals if str(row.get("sqlKey") or "").strip()}
    acceptance_by_sql_key = {str(row.get("sqlKey") or ""): row for row in acceptance if str(row.get("sqlKey") or "").strip()}
    patch_by_statement = {
        str(row.get("statementKey") or ""): row for row in patches if str(row.get("statementKey") or "").strip()
    }
    unverified_sql = {
        str(row.get("sql_key") or "")
        for row in verification_rows
        if str(row.get("status") or "").upper() == "UNVERIFIED" and str(row.get("sql_key") or "").strip()
    }
    ranked_rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "").strip()
        if not sql_key:
            continue
        statement_key = sql_key.split("#", 1)[0]
        proposal = proposal_by_sql_key.get(sql_key, {})
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        actionability = dict(proposal.get("actionability") or {})
        sql_verification_rows = [row for row in verification_rows if str(row.get("sql_key") or "").strip() == sql_key]
        outcome = assess_sql_outcome(
            [acceptance_row] if acceptance_row else [],
            [patch_row] if patch_row else [],
            sql_verification_rows,
        )
        evidence_layer, delivery_layer, acceptance_layer = _acceptance_decision_layers(acceptance_row)
        delivery_readiness = dict(acceptance_row.get("deliveryReadiness") or {})
        delivery_outcome = dict(patch_row.get("deliveryOutcome") or {})
        actionability_score = int(actionability.get("score") or 0)
        priority_score = actionability_score
        delivery_tier = str(outcome.get("delivery_assessment") or delivery_outcome.get("tier") or "").strip()
        readiness_tier = str(delivery_layer.get("tier") or delivery_readiness.get("tier") or "").strip()
        evidence_state = str(outcome.get("evidence_state") or "NONE").strip().upper()
        if delivery_tier == "READY_TO_APPLY":
            priority_score += 100
        elif delivery_tier == "PATCHABLE_WITH_REWRITE":
            priority_score += 70
        elif delivery_tier == "MANUAL_REVIEW":
            priority_score += 40
        elif patch_row.get("applicable") is True:
            priority_score += 100
            delivery_tier = "READY_TO_APPLY"
        elif readiness_tier == "READY":
            priority_score += 60
        elif readiness_tier == "NEEDS_TEMPLATE_REWRITE":
            priority_score += 35
        status = str(acceptance_layer.get("status") or acceptance_row.get("status") or "")
        if status == "PASS":
            priority_score += 20
        elif status == "NEED_MORE_PARAMS":
            priority_score += 5
        if evidence_state == "CRITICAL_GAP" or sql_key in unverified_sql:
            priority_score -= 50
        if evidence_state == "DEGRADED":
            priority_score -= 15
        if status == "FAIL":
            priority_score -= 20
        if priority_score >= 90:
            priority = "P0"
        elif priority_score >= 60:
            priority = "P1"
        else:
            priority = "P2"

        if str(delivery_outcome.get("summary") or "").strip():
            summary = str(delivery_outcome.get("summary") or "").strip()
        elif evidence_state == "CRITICAL_GAP":
            summary = "缺失关键验证证据；发布前请审查证据"
        elif bool(outcome.get("db_recheck_recommended")) or (
            bool(evidence_layer.get("degraded")) and str((acceptance_layer.get("feedbackReasonCode") or "")).strip() in {
            "VALIDATE_PARAM_INSUFFICIENT",
            "VALIDATE_DB_UNREACHABLE",
        }):
            summary = "验证证据已降级，需要数据库重新检查"
        elif patch_row.get("applicable") is True:
            summary = "补丁已就绪可应用"
        elif readiness_tier == "READY" or status == "PASS":
            summary = "重写已验证但补丁不可直接应用"
        elif readiness_tier == "NEEDS_TEMPLATE_REWRITE":
            summary = "验证路径存在但 mapper 需要模板感知重构"
        elif str(actionability.get("tier") or "") in {"HIGH", "MEDIUM"}:
            summary = "识别出高价值优化但尚未验证"
        else:
            summary = "低置信度或被阻塞的优化候选"

        if evidence_state == "CRITICAL_GAP":
            why_now = "缺失关键证据，因此在差距消除前保持高优先级"
        elif bool(outcome.get("db_recheck_recommended")):
            why_now = "主要阻塞是降级的数据库验证，而非重写本身"
        elif delivery_tier == "READY_TO_APPLY":
            why_now = "这是最快的安全收益，因为补丁已就绪"
        elif delivery_tier == "PATCHABLE_WITH_REWRITE":
            why_now = "在模板安全的 mapper 重构后立即成为高价值"
        elif delivery_tier == "MANUAL_REVIEW":
            why_now = "SQL 有前景，只需手动处理补丁冲突"
        elif delivery_tier == "NEEDS_REVIEW":
            why_now = "重写已验证，但补丁可应用性仍需人工决定"
        elif str(actionability.get("tier") or "") in {"HIGH", "MEDIUM"}:
            why_now = "具有强大潜力，但仍需更强的下游验证"
        else:
            why_now = "当前置信度低于领先候选"

        if not delivery_tier:
            if patch_row.get("applicable") is True:
                delivery_tier = "READY_TO_APPLY"
            elif readiness_tier == "READY":
                delivery_tier = "READY"
            elif readiness_tier == "NEEDS_TEMPLATE_REWRITE":
                delivery_tier = "NEEDS_TEMPLATE_REWRITE"
            else:
                delivery_tier = "BLOCKED"

        ranked_rows.append(
            {
                "sql_key": sql_key,
                "priority": priority,
                "actionability_tier": actionability.get("tier") or "LOW",
                "actionability_score": actionability_score,
                "delivery_tier": delivery_tier,
                "patch_applicable": patch_row.get("applicable"),
                "status": status or "PENDING",
                "summary": summary,
                "why_now": why_now,
                "evidence_state": evidence_state,
                "evidence_degraded": evidence_state == "DEGRADED",
                "acceptance_reason_code": str((outcome.get("feedback_reason_code") or (acceptance_layer.get("feedbackReasonCode") or ""))).strip() or None,
                "repair_hint_title": str(((((outcome.get("repair_hints") or [None])[0] or {}).get("title")) or "")).strip() or None,
                "repair_hint_command": str(((((outcome.get("repair_hints") or [None])[0] or {}).get("command")) or "")).strip() or None,
                "_priority_score": priority_score,
            }
        )
    ranked_rows.sort(key=lambda row: (-int(row.get("_priority_score") or 0), str(row.get("sql_key") or "")))
    return [{k: v for k, v in row.items() if k != "_priority_score"} for row in ranked_rows[:10]]


def summarize_actionability(
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
) -> dict[str, int]:
    proposal_tiers = [str((row.get("actionability") or {}).get("tier") or "").strip() for row in proposals]
    patch_by_statement = {
        str(row.get("statementKey") or ""): row for row in patches if str(row.get("statementKey") or "").strip()
    }
    needs_manual_review_count = 0
    for row in acceptance:
        if str(row.get("status") or "") != "PASS":
            continue
        sql_key = str(row.get("sqlKey") or "").strip()
        statement_key = sql_key.split("#", 1)[0] if sql_key else ""
        patch_row = patch_by_statement.get(statement_key, {})
        if patch_row.get("applicable") is not True:
            needs_manual_review_count += 1
    return {
        "high_value_sql_count": sum(1 for tier in proposal_tiers if tier in {"HIGH", "MEDIUM"}),
        "ready_to_apply_count": sum(1 for row in patches if row.get("applicable") is True),
        "needs_manual_review_count": needs_manual_review_count,
        "blocked_value_count": sum(1 for tier in proposal_tiers if tier == "BLOCKED"),
    }


def report_acceptance_llm_count(acceptance_rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in acceptance_rows if row.get("selectedCandidateSource") == "llm")
