from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable


RuleMatcher = Callable[[dict[str, Any]], bool]
SuggestionBuilder = Callable[[dict[str, Any]], list[dict[str, Any]]]


def _has_dollar_substitution(sql_unit: dict[str, Any]) -> bool:
    return "${" in str(sql_unit.get("sql") or "")


def _has_select_star(sql_unit: dict[str, Any]) -> bool:
    return "select *" in str(sql_unit.get("sql") or "").lower()


def _has_full_scan_risk(sql_unit: dict[str, Any]) -> bool:
    sql = str(sql_unit.get("sql") or "").lower()
    return " where " not in sql and str(sql_unit.get("statementType") or "").upper() == "SELECT"


def _select_star_suggestions(sql_unit: dict[str, Any]) -> list[dict[str, Any]]:
    sql = str(sql_unit.get("sql") or "")
    return [{"action": "PROJECT_COLUMNS", "sql": sql.replace("*", "id", 1)}]


_RULES: dict[str, dict[str, Any]] = {
    "DOLLAR_SUBSTITUTION": {
        "builtin": "core",
        "default_severity": "error",
        "message": "unsafe ${} dynamic substitution",
        "matcher": _has_dollar_substitution,
        "suggestions": None,
        "sets_verdict": True,
    },
    "SELECT_STAR": {
        "builtin": "performance",
        "default_severity": "warn",
        "message": "avoid select *",
        "matcher": _has_select_star,
        "suggestions": _select_star_suggestions,
        "sets_verdict": True,
    },
    "FULL_SCAN_RISK": {
        "builtin": "performance",
        "default_severity": "warn",
        "message": "no where filter",
        "matcher": _has_full_scan_risk,
        "suggestions": None,
        "sets_verdict": False,
    },
}

_BUILTIN_RULEPACKS = {
    "core": ["DOLLAR_SUBSTITUTION"],
    "performance": ["SELECT_STAR", "FULL_SCAN_RISK"],
}

DEFAULT_RULEPACKS = [{"builtin": "core"}, {"builtin": "performance"}]


def _match_declared_rule(sql_unit: dict[str, Any], match: dict[str, Any]) -> bool:
    sql = str(sql_unit.get("sql") or "")
    sql_lower = sql.lower()
    statement_type = str(sql_unit.get("statementType") or "").upper()
    dynamic_features = {str(x).strip().upper() for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()}

    sql_contains = str(match.get("sql_contains") or "")
    if sql_contains and sql_contains.lower() not in sql_lower:
        return False
    sql_regex = str(match.get("sql_regex") or "")
    if sql_regex and re.search(sql_regex, sql, flags=re.IGNORECASE) is None:
        return False
    statement_type_is = str(match.get("statement_type_is") or "").upper()
    if statement_type_is and statement_type != statement_type_is:
        return False
    dynamic_feature_has = str(match.get("dynamic_feature_has") or "").upper()
    if dynamic_feature_has and dynamic_feature_has not in dynamic_features:
        return False
    return True


def _evaluate_external_rule(sql_unit: dict[str, Any], rule: dict[str, Any], severity_overrides: dict[str, str]) -> dict[str, Any] | None:
    match = dict(rule.get("match") or {})
    if not _match_declared_rule(sql_unit, match):
        return None
    action = dict(rule.get("action") or {})
    rule_id = str(rule.get("rule_id") or "").strip()
    severity = severity_overrides.get(rule_id, str(rule.get("default_severity") or "warn"))
    suggestions: list[dict[str, Any]] = []
    suggestion_sql_template = str(action.get("suggestion_sql_template") or "").strip()
    if suggestion_sql_template:
        suggestions.append({"action": "CUSTOM_SQL_TEMPLATE", "sql": suggestion_sql_template})
    return {
        "issue": {
            "code": rule_id,
            "message": str(rule.get("message") or "").strip(),
            "severity": severity,
        },
        "triggered_rule": {
            "ruleId": rule_id,
            "builtin": "file",
            "severity": severity,
            "sourceRef": str(rule.get("source_ref") or "").strip() or None,
            "blocksActionability": bool(action.get("block_actionability", False)),
        },
        "suggestions": suggestions,
        "sets_verdict": True,
    }


def configured_rule_ids(config: dict[str, Any]) -> list[str]:
    diagnostics_cfg = dict(config.get("diagnostics") or {})
    configured = diagnostics_cfg.get("rulepacks") or DEFAULT_RULEPACKS
    disabled = {str(x).strip() for x in (diagnostics_cfg.get("disabled_rules") or []) if str(x).strip()}
    ordered: list[str] = []
    for entry in configured:
        if not isinstance(entry, dict):
            continue
        builtin = str(entry.get("builtin") or "").strip()
        if not builtin:
            continue
        for rule_id in _BUILTIN_RULEPACKS.get(builtin, []):
            if rule_id not in disabled and rule_id not in ordered:
                ordered.append(rule_id)
    return ordered


def evaluate_rules(sql_unit: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    diagnostics_cfg = dict(config.get("diagnostics") or {})
    severity_overrides = {
        str(k).strip(): str(v).strip().lower()
        for k, v in dict(diagnostics_cfg.get("severity_overrides") or {}).items()
        if str(k).strip() and str(v).strip()
    }
    issues: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    triggered_rules: list[dict[str, Any]] = []
    verdict = "NOOP"

    for rule_id in configured_rule_ids(config):
        rule = _RULES.get(rule_id)
        if not rule:
            continue
        matcher = rule["matcher"]
        if not matcher(sql_unit):
            continue
        severity = severity_overrides.get(rule_id, rule["default_severity"])
        issue = {"code": rule_id, "message": rule["message"], "severity": severity}
        issues.append(issue)
        triggered_rules.append(
            {
                "ruleId": rule_id,
                "builtin": rule["builtin"],
                "severity": severity,
            }
        )
        suggestion_builder = rule["suggestions"]
        if suggestion_builder is not None:
            suggestions.extend(suggestion_builder(sql_unit))
        if rule.get("sets_verdict"):
            verdict = "CAN_IMPROVE"

    loaded_rulepacks = [row for row in (diagnostics_cfg.get("loaded_rulepacks") or []) if isinstance(row, dict)]
    loaded_by_file = {
        str(row.get("file") or "").strip(): [rule for rule in (row.get("rules") or []) if isinstance(rule, dict)]
        for row in loaded_rulepacks
        if str(row.get("file") or "").strip()
    }
    for entry in diagnostics_cfg.get("rulepacks") or DEFAULT_RULEPACKS:
        if not isinstance(entry, dict):
            continue
        file_ref = str(entry.get("file") or "").strip()
        if not file_ref:
            continue
        for rule in loaded_by_file.get(file_ref, []):
            rule_with_source = {**rule, "source_ref": file_ref}
            result = _evaluate_external_rule(sql_unit, rule_with_source, severity_overrides)
            if result is None:
                continue
            issues.append(result["issue"])
            triggered_rules.append(result["triggered_rule"])
            suggestions.extend(result["suggestions"])
            if result.get("sets_verdict"):
                verdict = "CAN_IMPROVE"

    return {
        "issues": issues,
        "suggestions": suggestions,
        "verdict": verdict,
        "triggeredRules": triggered_rules,
    }


def load_llm_feedback(run_dir: Path) -> list[dict[str, Any]]:
    """加载 LLM 反馈记录

    从运行目录中加载之前运行收集的 LLM 反馈。

    Args:
        run_dir: 运行目录

    Returns:
        反馈记录列表
    """
    feedback_file = run_dir / "ops" / "llm_feedback.jsonl"
    if not feedback_file.exists():
        return []

    feedback_records: list[dict[str, Any]] = []
    with open(feedback_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    feedback_records.append(record)
                except json.JSONDecodeError:
                    continue

    return feedback_records


def analyze_llm_feedback_for_rules(
    feedback_records: list[dict[str, Any]],
    current_rules: list[str],
) -> dict[str, Any]:
    """分析 LLM 反馈以发现规则未覆盖的问题

    比较 LLM 发现的问题与当前规则触发的情况，找出规则引擎可能遗漏的模式。

    Args:
        feedback_records: LLM 反馈记录列表
        current_rules: 当前启用的规则 ID 列表

    Returns:
        分析结果字典
    """
    # 统计 LLM 发现但规则未覆盖的情况
    llm_only_issues: list[dict[str, Any]] = []
    rule_missed_counts: dict[str, int] = {}

    for record in feedback_records:
        llm_issues = record.get("llm_detected_issues", [])
        triggered = set(record.get("triggered_rules", []))

        if llm_issues and not triggered:
            # LLM 发现了问题但没有规则被触发
            for issue in llm_issues:
                issue_type = issue.get("type", "unknown")
                if issue_type not in rule_missed_counts:
                    rule_missed_counts[issue_type] = 0
                rule_missed_counts[issue_type] += 1

                llm_only_issues.append({
                    "sql_key": record.get("sql_key"),
                    "issue_type": issue_type,
                    "description": issue.get("description", ""),
                    "acceptance_status": record.get("acceptance_status"),
                })

    # 统计各规则的覆盖率
    rule_coverage: dict[str, dict[str, int]] = {}
    for record in feedback_records:
        triggered = record.get("triggered_rules", [])
        for rule_id in triggered:
            if rule_id not in rule_coverage:
                rule_coverage[rule_id] = {"triggered": 0, "with_llm_issue": 0}
            rule_coverage[rule_id]["triggered"] += 1

            # 如果同时 LLM 也发现了问题
            if record.get("llm_detected_issues"):
                rule_coverage[rule_id]["with_llm_issue"] += 1

    return {
        "llm_only_issues": llm_only_issues,
        "llm_only_issue_types": rule_missed_counts,
        "rule_coverage": rule_coverage,
        "total_records_analyzed": len(feedback_records),
        "records_with_llm_issues": sum(1 for r in feedback_records if r.get("llm_detected_issues")),
        "records_with_triggered_rules": sum(1 for r in feedback_records if r.get("triggered_rules")),
    }


def get_feedback_based_suggestions(
    feedback_records: list[dict[str, Any]],
    sql_unit: dict[str, Any],
) -> list[dict[str, Any]]:
    """基于历史反馈生成建议

    查看历史反馈中类似 SQL 的处理方式，提供建议。

    Args:
        feedback_records: LLM 反馈记录列表
        sql_unit: 当前 SQL 单元

    Returns:
        建议列表
    """
    suggestions: list[dict[str, Any]] = []

    current_sql = str(sql_unit.get("sql", "")).lower()
    current_sql_key = str(sql_unit.get("sqlKey", ""))

    # 查找类似的 SQL 处理案例
    for record in feedback_records:
        # 跳过当前 SQL
        if record.get("sql_key") == current_sql_key:
            continue

        # 查看是否有类似的 LLM 发现
        for issue in record.get("llm_detected_issues", []):
            issue_desc = str(issue.get("description", "")).lower()

            # 简单的相似性检查：是否包含共同的关键词
            if any(kw in current_sql for kw in ["join", "where", "select"]):
                if issue.get("type") == "performance" and "index" in issue_desc:
                    suggestions.append({
                        "action": "FEEDBACK_BASED_SUGGESTION",
                        "type": "performance",
                        "message": f"Similar SQL had performance issue: {issue_desc[:100]}",
                        "reference_sql_key": record.get("sql_key"),
                    })
                    break

    return suggestions
