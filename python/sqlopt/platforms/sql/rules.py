from __future__ import annotations

import re
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
