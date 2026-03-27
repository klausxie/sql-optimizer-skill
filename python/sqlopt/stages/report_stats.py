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


def _normalize_delivery_status(tier: str) -> str:
    normalized = str(tier or "").strip().upper()
    if normalized in {"READY_TO_APPLY", "PATCHABLE_WITH_REWRITE", "MANUAL_REVIEW", "NEEDS_REVIEW", "BLOCKED"}:
        return normalized
    if normalized == "READY":
        return "NEEDS_REVIEW"
    if normalized == "NEEDS_TEMPLATE_REWRITE":
        return "PATCHABLE_WITH_REWRITE"
    return "BLOCKED"


def _primary_blocker_message(code: str | None) -> str | None:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return None
    if normalized.startswith("AGGREGATION_CONSTRAINT:"):
        return "aggregation semantics require an explicit safe rule before automatic patch delivery"
    if normalized == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "unsafe ${} dynamic SQL blocks automatic patch generation"
    if normalized == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
        return "semantic confidence is LOW and delivery is blocked until stronger evidence is collected"
    if normalized.startswith("SEMANTIC_GATE_"):
        return "semantic gate is not PASS and blocks downstream patch delivery"
    if normalized == "VERIFICATION_CRITICAL_GAP":
        return "critical verification evidence is missing for this SQL"
    if normalized == "VALIDATE_DB_UNREACHABLE":
        return "database-backed validation is degraded; rerun with healthy connectivity"
    if normalized.startswith("PATCH_"):
        return "patch decision logic blocked automatic delivery for this SQL"
    return normalized


def _patch_apply_ready(patch_row: dict[str, Any]) -> bool:
    delivery_stage = str(patch_row.get("deliveryStage") or "").strip().upper()
    if delivery_stage:
        return delivery_stage == "APPLY_READY"
    return patch_row.get("applicable") is True


def blocker_family_for_outcome(
    *,
    delivery_status: str,
    blocker_primary_code: str | None,
    semantic_gate_status: str | None,
) -> str:
    normalized_delivery = _normalize_delivery_status(delivery_status)
    normalized_code = str(blocker_primary_code or "").strip().upper()
    normalized_gate = str(semantic_gate_status or "").strip().upper()
    if normalized_delivery == "READY_TO_APPLY":
        return "READY"
    if normalized_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "SECURITY"
    if normalized_gate == "FAIL" or normalized_code in {
        "SEMANTIC_GATE_FAIL",
        "VALIDATE_EQUIVALENCE_MISMATCH",
        "VALIDATE_SEMANTIC_ERROR",
        "VALIDATE_SEMANTIC_CONFIDENCE_LOW",
        "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        "PATCH_SEMANTIC_CONFIDENCE_LOW",
    }:
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def _aggregation_profile(acceptance_row: dict[str, Any]) -> dict[str, Any]:
    aggregation = dict(((acceptance_row.get("rewriteFacts") or {}).get("aggregationQuery") or {}))
    profile = dict(aggregation.get("capabilityProfile") or {})
    return {
        "shape_family": str(profile.get("shapeFamily") or "NONE").strip().upper(),
        "capability_tier": str(profile.get("capabilityTier") or "NONE").strip().upper(),
        "constraint_family": str(profile.get("constraintFamily") or "NONE").strip().upper(),
        "safe_baseline_family": str(profile.get("safeBaselineFamily") or "").strip() or None,
    }


def _dynamic_template_profile(acceptance_row: dict[str, Any], patch_row: dict[str, Any] | None = None) -> dict[str, Any]:
    dynamic_template = dict((acceptance_row.get("dynamicTemplate") or {}) or {})
    if dynamic_template:
        return {
            "shape_family": str(dynamic_template.get("shapeFamily") or "NONE").strip().upper(),
            "capability_tier": str(dynamic_template.get("capabilityTier") or "NONE").strip().upper(),
            "patch_surface": str(dynamic_template.get("patchSurface") or "NONE").strip().upper(),
            "baseline_family": str(dynamic_template.get("baselineFamily") or "").strip() or None,
            "blocking_reason": str(dynamic_template.get("blockingReason") or "").strip().upper() or None,
            "delivery_class": str(dynamic_template.get("deliveryClass") or "").strip().upper() or None,
        }

    rewrite_facts = dict((acceptance_row.get("rewriteFacts") or {}) or {})
    facts = dict((rewrite_facts.get("dynamicTemplate") or {}) or {})
    profile = dict((facts.get("capabilityProfile") or {}) or {})
    if not facts:
        return {
            "shape_family": "NONE",
            "capability_tier": "NONE",
            "patch_surface": "NONE",
            "baseline_family": None,
            "blocking_reason": None,
            "delivery_class": None,
        }
    capability_tier = str(profile.get("capabilityTier") or "NONE").strip().upper()
    patch_payload = dict(patch_row or {})
    blocking_reason = (
        str(patch_payload.get("dynamicTemplateBlockingReason") or "").strip().upper()
        or str(profile.get("blockerFamily") or "").strip().upper()
        or None
    )
    strategy_type = str((patch_payload.get("dynamicTemplateStrategy") or patch_payload.get("strategyType") or "")).strip().upper()
    delivery_class = None
    delivery_stage = str(patch_payload.get("deliveryStage") or "").strip().upper()
    patch_apply_ready = delivery_stage == "APPLY_READY" if delivery_stage else patch_payload.get("applicable") is True
    if strategy_type.startswith("DYNAMIC_") and patch_apply_ready:
        delivery_class = "READY_DYNAMIC_PATCH"
    elif capability_tier == "SAFE_BASELINE" and blocking_reason and blocking_reason.endswith("NO_EFFECTIVE_DIFF"):
        delivery_class = "SAFE_BASELINE_NO_DIFF"
    elif capability_tier == "SAFE_BASELINE":
        delivery_class = "SAFE_BASELINE_BLOCKED"
    elif str(profile.get("shapeFamily") or "").strip():
        delivery_class = "REVIEW_ONLY"
    return {
        "shape_family": str(profile.get("shapeFamily") or "NONE").strip().upper(),
        "capability_tier": capability_tier,
        "patch_surface": str(profile.get("patchSurface") or "NONE").strip().upper(),
        "baseline_family": str(profile.get("baselineFamily") or "").strip() or None,
        "blocking_reason": blocking_reason,
        "delivery_class": delivery_class,
    }


def _pick_primary_blocker(
    *,
    delivery_status: str,
    evidence_state: str,
    critical_gaps: list[str],
    semantic_blocked_reason: str | None,
    acceptance_reason_code: str | None,
    patch_selection_code: str | None,
) -> tuple[str | None, str | None, str | None]:
    code: str | None = None
    phase: str | None = None
    if evidence_state == "CRITICAL_GAP":
        code = str((critical_gaps or [None])[0] or "VERIFICATION_CRITICAL_GAP").strip().upper()
        phase = "verification"
    elif semantic_blocked_reason in {"VALIDATE_SEMANTIC_CONFIDENCE_LOW", "SEMANTIC_GATE_FAIL", "SEMANTIC_GATE_UNCERTAIN"}:
        code = str(semantic_blocked_reason).strip().upper()
        phase = "validate"
    elif acceptance_reason_code:
        code = str(acceptance_reason_code).strip().upper()
        phase = "validate"
    elif patch_selection_code:
        code = str(patch_selection_code).strip().upper()
        phase = "patch_generate"
    elif delivery_status == "BLOCKED":
        code = "DELIVERY_BLOCKED"
        phase = "patch_generate"
    return code, phase, _primary_blocker_message(code)


def _derive_evidence_availability(
    *,
    acceptance_row: dict[str, Any],
    semantic_gate: dict[str, Any],
    evidence_state: str,
    blocker_primary_code: str | None,
) -> tuple[str, str | None, str | None]:
    code = str(blocker_primary_code or "").strip().upper()
    if evidence_state == "CRITICAL_GAP":
        return "MISSING", "CRITICAL_GAP_UNVERIFIED_OUTPUT", "补齐关键验证证据并重跑 report"
    if code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "MISSING", "SKIPPED_BY_SECURITY_BLOCK", "移除 ${} 动态 SQL（改为参数绑定+白名单）后重跑"
    equivalence = dict(acceptance_row.get("equivalence") or {})
    checked = equivalence.get("checked")
    refs = [str(x) for x in (equivalence.get("evidenceRefs") or []) if str(x).strip()]
    evidence_level = str(semantic_gate.get("evidenceLevel") or "").strip().upper()
    if checked is True and refs:
        return "READY", None, None
    if checked is True and evidence_level in {"DB_FINGERPRINT", "DB_COUNT"}:
        return "READY", None, None
    if checked is True:
        return "PARTIAL", "STRUCTURE_ONLY_OR_REFERENCE_MISSING", "补充数据库语义证据（DB_COUNT/DB_FINGERPRINT）"
    if checked is False or checked is None:
        return "MISSING", "SEMANTIC_EVIDENCE_NOT_COLLECTED", "恢复语义校验并重跑 validate"
    return "PARTIAL", "EVIDENCE_STATE_UNCERTAIN", "人工审查 acceptance 与 verification 证据"


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
        delivery_tier = str(top_row.get("delivery_status") or top_row.get("delivery_tier") or "").strip().upper()
        evidence_state = str(top_row.get("evidence_state") or "").strip().upper()
        evidence_degraded = evidence_state == "DEGRADED" or bool(top_row.get("evidence_degraded"))
        critical_gap = evidence_state == "CRITICAL_GAP"
        acceptance_reason_code = str(top_row.get("acceptance_reason_code") or "").strip().upper()
        blocker_primary_code = str(top_row.get("blocker_primary_code") or "").strip().upper()
        aggregation_constraint_family = str(top_row.get("aggregation_constraint_family") or "").strip().upper()
        hint_command = str(top_row.get("repair_hint_command") or "").strip() or None
        if blocker_primary_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
            _append_action_once(
                actions,
                {
                    "action_id": "remove-dollar",
                    "title": "后端：移除 ${} 动态 SQL",
                    "reason": action_reason("remove-dollar"),
                    "applicability": "主阻断是 SQL 安全规则",
                    "expected_outcome": "解除安全阻断，恢复候选与补丁路径",
                    "commands": ['rg -n "\\$\\{" src/main/resources/**/*.xml'],
                },
            )
        elif aggregation_constraint_family not in {"", "NONE", "SAFE_BASELINE"}:
            aggregation_action_map = {
                "DISTINCT_RELAXATION": {
                    "action_id": "review-distinct-safety",
                    "title": "架构：补齐 DISTINCT safe rule",
                    "reason": "当前阻断点是 DISTINCT 放宽语义，必须先建立显式等价白名单",
                    "expected_outcome": "把 DISTINCT 场景区分为 safe wrapper flatten 与 direct relaxation 两类",
                },
                "GROUP_BY_AGGREGATION": {
                    "action_id": "review-groupby-safety",
                    "title": "架构：补齐 GROUP BY safe rule",
                    "reason": "当前阻断点是 GROUP BY 聚合语义缺少稳定 safe baseline",
                    "expected_outcome": "为可证明等价的 GROUP BY 子类建立统一安全门限",
                },
                "HAVING_AGGREGATION": {
                    "action_id": "review-having-safety",
                    "title": "架构：补齐 HAVING safe rule",
                    "reason": "当前阻断点是 HAVING 聚合语义尚未收敛到可自动交付的白名单",
                    "expected_outcome": "把 HAVING 场景拆成可自动 flatten 的 safe 子类与继续阻断的复杂子类",
                },
                "WINDOW_AGGREGATION": {
                    "action_id": "review-window-safety",
                    "title": "架构：补齐 WINDOW safe rule",
                    "reason": "当前阻断点是窗口函数语义复杂，尚无自动补丁白名单",
                    "expected_outcome": "先明确哪些 window shape 一律阻断，哪些可进入后续能力路线图",
                },
                "UNION_AGGREGATION": {
                    "action_id": "review-union-safety",
                    "title": "架构：补齐 UNION safe rule",
                    "reason": "当前阻断点是 UNION 分支语义未纳入自动补丁安全框架",
                    "expected_outcome": "先定义 UNION 的结构化约束，再决定是否存在 safe baseline",
                },
            }
            action = aggregation_action_map.get(
                aggregation_constraint_family,
                {
                    "action_id": "review-aggregation-safety",
                    "title": "架构：补齐聚合语义 safe rule",
                    "reason": "聚合语义当前没有显式 safe baseline，自动补丁仍被约束层阻断",
                    "expected_outcome": "把该聚合 shape 从 REVIEW_REQUIRED 收敛到 SAFE_BASELINE 或明确继续阻断",
                },
            )
            _append_action_once(
                actions,
                {
                    "action_id": action["action_id"],
                    "title": action["title"],
                    "reason": action["reason"],
                    "applicability": "优先项命中聚合语义约束族",
                    "expected_outcome": action["expected_outcome"],
                    "commands": [],
                },
            )
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


def _infer_semantic_unupgraded_reason(semantic_gate: dict[str, Any]) -> str | None:
    if not isinstance(semantic_gate, dict):
        return "SEMANTIC_GATE_MISSING"
    if bool(semantic_gate.get("confidenceUpgradeApplied")):
        return None
    hard_conflicts = [str(code or "").strip() for code in (semantic_gate.get("hardConflicts") or []) if str(code or "").strip()]
    if hard_conflicts:
        return f"HARD_CONFLICT:{hard_conflicts[0]}"
    confidence = str(semantic_gate.get("confidence") or "").strip().upper()
    if confidence in {"MEDIUM", "HIGH"}:
        return "ALREADY_CONFIDENT"
    evidence = dict(semantic_gate.get("evidence") or {})
    fingerprint_strength = str(evidence.get("fingerprintStrength") or "").strip().upper()
    row_count_status = str(evidence.get("rowCountStatus") or "").strip().upper()
    if fingerprint_strength in {"EXACT", "PARTIAL"}:
        return "UPGRADE_NOT_NEEDED"
    if row_count_status in {"", "SKIPPED", "ERROR"}:
        return "DB_EVIDENCE_MISSING"
    if fingerprint_strength in {"NONE", "MISMATCH", "MISMATCH_SAMPLE"}:
        return "FINGERPRINT_NOT_MATCHED"
    return "UPGRADE_CRITERIA_NOT_MET"


def _infer_semantic_blocked_reason(acceptance_row: dict[str, Any], semantic_gate: dict[str, Any]) -> str | None:
    status = str(semantic_gate.get("status") or "PASS").strip().upper()
    confidence = str(semantic_gate.get("confidence") or "HIGH").strip().upper()
    if status != "PASS":
        return f"SEMANTIC_GATE_{status}"
    if confidence == "LOW":
        return "VALIDATE_SEMANTIC_CONFIDENCE_LOW"
    acceptance_status = str(acceptance_row.get("status") or "").strip().upper()
    if acceptance_status != "PASS":
        feedback = dict(acceptance_row.get("feedback") or {})
        return str(feedback.get("reason_code") or acceptance_status)
    return None


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
        semantic_gate = dict(acceptance_row.get("semanticEquivalence") or {})
        semantic_upgrade_applied = bool(semantic_gate.get("confidenceUpgradeApplied"))
        rows.append(
            {
                "sql_key": sql_key,
                "status": acceptance_row.get("status") or "PENDING",
                "selected_source": acceptance_row.get("selectedCandidateSource") or "n/a",
                "semantic_risk": acceptance_row.get("semanticRisk") or "unknown",
                "perf_improved": perf.get("improved"),
                "before_cost": (perf.get("beforeSummary") or {}).get("totalCost"),
                "after_cost": (perf.get("afterSummary") or {}).get("totalCost"),
                "patch_applicable": _patch_apply_ready(patch_row),
                "patch_selection_code": (patch_row.get("selectionReason") or {}).get("code"),
                "rewrite_materialization_mode": (acceptance_row.get("rewriteMaterialization") or {}).get("mode"),
                "rewrite_materialization_reason": (acceptance_row.get("rewriteMaterialization") or {}).get("reasonCode"),
                "row_status": (eq.get("rowCount") or {}).get("status"),
                "evidence_refs": eq.get("evidenceRefs") or [],
                "semantic_gate_status": semantic_gate.get("status") or "UNKNOWN",
                "semantic_gate_confidence": semantic_gate.get("confidence") or "UNKNOWN",
                "semantic_gate_evidence_level": semantic_gate.get("evidenceLevel") or "UNKNOWN",
                "semantic_confidence_before_upgrade": semantic_gate.get("confidenceBeforeUpgrade"),
                "semantic_confidence_upgraded": semantic_upgrade_applied,
                "semantic_upgrade_reasons": semantic_gate.get("confidenceUpgradeReasons") or [],
                "semantic_upgrade_sources": semantic_gate.get("confidenceUpgradeEvidenceSources") or [],
                "semantic_hard_conflicts": semantic_gate.get("hardConflicts") or [],
                "semantic_unupgraded_reason": _infer_semantic_unupgraded_reason(semantic_gate),
                "semantic_blocked_reason": _infer_semantic_blocked_reason(acceptance_row, semantic_gate),
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
        diagnostics = dict(proposal.get("candidateGenerationDiagnostics") or {})
        rows.append(
            {
                "sql_key": str(proposal.get("sqlKey") or ""),
                "verdict": str(proposal.get("verdict") or "UNKNOWN"),
                "issue_codes": issue_codes,
                "llm_candidate_count": len(proposal.get("llmCandidates") or []),
                "candidate_degradation_kind": str(diagnostics.get("degradationKind") or "").strip() or None,
                "candidate_recovery_strategy": str(diagnostics.get("recoveryStrategy") or "").strip() or None,
                "candidate_recovery_succeeded": bool(diagnostics.get("recoverySucceeded")),
                "candidate_pruned_low_value_count": int(diagnostics.get("prunedLowValueCount") or 0),
            }
        )
    return rows


def build_top_actionable_sql(
    units: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
    *,
    limit: int | None = 10,
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
        semantic_gate = dict(acceptance_row.get("semanticEquivalence") or {})
        semantic_blocked_reason = _infer_semantic_blocked_reason(acceptance_row, semantic_gate)
        semantic_unupgraded_reason = _infer_semantic_unupgraded_reason(semantic_gate)
        patch_row = patch_by_statement.get(statement_key, {})
        aggregation_profile = _aggregation_profile(acceptance_row)
        dynamic_profile = _dynamic_template_profile(acceptance_row, patch_row)
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
        elif _patch_apply_ready(patch_row):
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
        if semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
            priority_score -= 10
        if priority_score >= 90:
            priority = "P0"
        elif priority_score >= 60:
            priority = "P1"
        else:
            priority = "P2"

        if not delivery_tier:
            if _patch_apply_ready(patch_row):
                delivery_tier = "READY_TO_APPLY"
            elif readiness_tier == "READY":
                delivery_tier = "READY"
            elif readiness_tier == "NEEDS_TEMPLATE_REWRITE":
                delivery_tier = "NEEDS_TEMPLATE_REWRITE"
            else:
                delivery_tier = "BLOCKED"
        delivery_status = _normalize_delivery_status(delivery_tier)
        delivery_tier = delivery_status

        acceptance_reason_code = str(
            (outcome.get("feedback_reason_code") or (acceptance_layer.get("feedbackReasonCode") or ""))
        ).strip() or None
        patch_selection_code = str(((patch_row.get("selectionReason") or {}).get("code") or "")).strip() or None
        blocker_primary_code, blocker_primary_phase, blocker_primary_message = _pick_primary_blocker(
            delivery_status=delivery_status,
            evidence_state=evidence_state,
            critical_gaps=list(outcome.get("critical_gaps") or []),
            semantic_blocked_reason=semantic_blocked_reason,
            acceptance_reason_code=acceptance_reason_code,
            patch_selection_code=patch_selection_code,
        )
        evidence_availability, evidence_missing_reason, evidence_next_required = _derive_evidence_availability(
            acceptance_row=acceptance_row,
            semantic_gate=semantic_gate,
            evidence_state=evidence_state,
            blocker_primary_code=blocker_primary_code,
        )

        if aggregation_profile["constraint_family"] not in {"", "NONE", "SAFE_BASELINE"}:
            summary = "聚合语义仍处于受限能力面，需显式 safe rule 后才能自动交付"
        elif blocker_primary_code and str(blocker_primary_code).startswith("AGGREGATION_CONSTRAINT:"):
            summary = "聚合语义仍处于受限能力面，需显式 safe rule 后才能自动交付"
        elif blocker_primary_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
            summary = "检测到 ${} 动态 SQL，自动补丁被安全策略阻断"
        elif str(delivery_outcome.get("summary") or "").strip():
            summary = str(delivery_outcome.get("summary") or "").strip()
        elif evidence_state == "CRITICAL_GAP":
            summary = "缺失关键验证证据；发布前请审查证据"
        elif bool(outcome.get("db_recheck_recommended")) or (
            bool(evidence_layer.get("degraded")) and str((acceptance_layer.get("feedbackReasonCode") or "")).strip() in {
            "VALIDATE_PARAM_INSUFFICIENT",
            "VALIDATE_DB_UNREACHABLE",
        }):
            summary = "验证证据已降级，需要数据库重新检查"
        elif _patch_apply_ready(patch_row):
            summary = "补丁已就绪可应用"
        elif semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
            summary = "语义门置信度偏低，需补充 DB 指纹证据后再交付"
        elif str(semantic_blocked_reason or "").startswith("SEMANTIC_GATE_"):
            summary = "语义门未通过，需先解决语义冲突或不确定项"
        elif readiness_tier == "READY" or status == "PASS":
            summary = "重写已验证但补丁不可直接应用"
        elif readiness_tier == "NEEDS_TEMPLATE_REWRITE":
            summary = "验证路径存在但 mapper 需要模板感知重构"
        elif str(actionability.get("tier") or "") in {"HIGH", "MEDIUM"}:
            summary = "识别出高价值优化但尚未验证"
        else:
            summary = "低置信度或被阻塞的优化候选"

        if aggregation_profile["constraint_family"] not in {"", "NONE", "SAFE_BASELINE"}:
            why_now = "当前主要差距是聚合语义能力边界，而不是模板编辑本身"
        elif blocker_primary_code and str(blocker_primary_code).startswith("AGGREGATION_CONSTRAINT:"):
            why_now = "当前主要差距是聚合语义能力边界，而不是模板编辑本身"
        elif blocker_primary_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
            why_now = "先移除 ${} 安全阻断，再恢复候选评估与补丁生成"
        elif evidence_state == "CRITICAL_GAP":
            why_now = "缺失关键证据，因此在差距消除前保持高优先级"
        elif bool(outcome.get("db_recheck_recommended")):
            why_now = "主要阻塞是降级的数据库验证，而非重写本身"
        elif delivery_status == "READY_TO_APPLY":
            why_now = "这是最快的安全收益，因为补丁已就绪"
        elif semantic_blocked_reason == "VALIDATE_SEMANTIC_CONFIDENCE_LOW":
            why_now = "当前主要差距是语义证据强度不足，而不是改写本身"
        elif str(semantic_blocked_reason or "").startswith("SEMANTIC_GATE_"):
            why_now = "先消除语义门阻塞，再评估交付路径"
        elif delivery_status == "PATCHABLE_WITH_REWRITE":
            why_now = "在模板安全的 mapper 重构后立即成为高价值"
        elif delivery_status == "MANUAL_REVIEW":
            why_now = "SQL 有前景，只需手动处理补丁冲突"
        elif delivery_status == "NEEDS_REVIEW":
            why_now = "重写已验证，但补丁可应用性仍需人工决定"
        elif str(actionability.get("tier") or "") in {"HIGH", "MEDIUM"}:
            why_now = "具有强大潜力，但仍需更强的下游验证"
        else:
            why_now = "当前置信度低于领先候选"

        ranked_rows.append(
            {
                "sql_key": sql_key,
                "priority": priority,
                "actionability_tier": actionability.get("tier") or "LOW",
                "actionability_score": actionability_score,
                "delivery_status": delivery_status,
                "delivery_tier": delivery_tier,
                "patch_applicable": _patch_apply_ready(patch_row),
                "status": status or "PENDING",
                "summary": summary,
                "why_now": why_now,
                "evidence_state": evidence_state,
                "evidence_degraded": evidence_state == "DEGRADED",
                "evidence_availability": evidence_availability,
                "evidence_missing_reason": evidence_missing_reason,
                "evidence_next_required": evidence_next_required,
                "blocker_primary_code": blocker_primary_code,
                "blocker_family": blocker_family_for_outcome(
                    delivery_status=delivery_status,
                    blocker_primary_code=blocker_primary_code,
                    semantic_gate_status=semantic_gate.get("status") or "UNKNOWN",
                ),
                "blocker_primary_phase": blocker_primary_phase,
                "blocker_primary_message": blocker_primary_message,
                "aggregation_shape_family": aggregation_profile["shape_family"],
                "aggregation_capability_tier": aggregation_profile["capability_tier"],
                "aggregation_constraint_family": aggregation_profile["constraint_family"],
                "aggregation_safe_baseline_family": aggregation_profile["safe_baseline_family"],
                "dynamic_shape_family": dynamic_profile["shape_family"],
                "dynamic_capability_tier": dynamic_profile["capability_tier"],
                "dynamic_patch_surface": dynamic_profile["patch_surface"],
                "dynamic_baseline_family": dynamic_profile["baseline_family"],
                "dynamic_blocking_reason": dynamic_profile["blocking_reason"],
                "dynamic_delivery_class": dynamic_profile["delivery_class"],
                "acceptance_reason_code": acceptance_reason_code,
                "repair_hint_title": str(((((outcome.get("repair_hints") or [None])[0] or {}).get("title")) or "")).strip() or None,
                "repair_hint_command": str(((((outcome.get("repair_hints") or [None])[0] or {}).get("command")) or "")).strip() or None,
                "semantic_gate_status": semantic_gate.get("status") or "UNKNOWN",
                "semantic_gate_confidence": semantic_gate.get("confidence") or "UNKNOWN",
                "semantic_gate_evidence_level": semantic_gate.get("evidenceLevel") or "UNKNOWN",
                "semantic_confidence_before_upgrade": semantic_gate.get("confidenceBeforeUpgrade"),
                "semantic_confidence_upgraded": bool(semantic_gate.get("confidenceUpgradeApplied")),
                "semantic_upgrade_reasons": semantic_gate.get("confidenceUpgradeReasons") or [],
                "semantic_upgrade_sources": semantic_gate.get("confidenceUpgradeEvidenceSources") or [],
                "semantic_hard_conflicts": semantic_gate.get("hardConflicts") or [],
                "semantic_unupgraded_reason": semantic_unupgraded_reason,
                "semantic_blocked_reason": semantic_blocked_reason,
                "patch_selection_code": patch_selection_code,
                "_priority_score": priority_score,
            }
        )
    ranked_rows.sort(key=lambda row: (-int(row.get("_priority_score") or 0), str(row.get("sql_key") or "")))
    if limit is None:
        selected = ranked_rows
    else:
        selected = ranked_rows[: max(int(limit), 0)]
    return [{k: v for k, v in row.items() if k != "_priority_score"} for row in selected]


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
        if not _patch_apply_ready(patch_row):
            needs_manual_review_count += 1
    return {
        "high_value_sql_count": sum(1 for tier in proposal_tiers if tier in {"HIGH", "MEDIUM"}),
        "ready_to_apply_count": sum(1 for row in patches if _patch_apply_ready(row)),
        "needs_manual_review_count": needs_manual_review_count,
        "blocked_value_count": sum(1 for tier in proposal_tiers if tier == "BLOCKED"),
    }


def report_acceptance_llm_count(acceptance_rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in acceptance_rows if row.get("selectedCandidateSource") == "llm")
