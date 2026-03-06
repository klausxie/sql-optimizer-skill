from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from .common import load_raw

RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _load_diagnostics_rule_file(path: Path) -> list[dict[str, Any]]:
    data = load_raw(path)
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ConfigError(f"diagnostics rule file must define a rules array: {path}")
    normalized_rules: list[dict[str, Any]] = []
    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            raise ConfigError(f"diagnostics rule entries must be objects: {path}")
        rule_id = str(raw_rule.get("rule_id") or "").strip()
        if not RULE_ID_RE.match(rule_id):
            raise ConfigError(f"diagnostics rule_id must match {RULE_ID_RE.pattern}: {path}")
        message = str(raw_rule.get("message") or "").strip()
        if not message:
            raise ConfigError(f"diagnostics rule message is required: {path}")
        default_severity = str(raw_rule.get("default_severity") or "warn").strip().lower()
        if default_severity not in {"info", "warn", "error"}:
            raise ConfigError(f"diagnostics default_severity must be one of: info, warn, error ({path})")

        match = raw_rule.get("match")
        if not isinstance(match, dict):
            raise ConfigError(f"diagnostics rule match must be object: {path}")
        allowed_match_keys = {"sql_contains", "sql_regex", "statement_type_is", "dynamic_feature_has"}
        unknown_match_keys = sorted(set(match.keys()) - allowed_match_keys)
        if unknown_match_keys:
            raise ConfigError(f"diagnostics rule match contains unsupported keys {unknown_match_keys}: {path}")
        normalized_match: dict[str, Any] = {}
        sql_contains = str(match.get("sql_contains") or "").strip()
        if sql_contains:
            normalized_match["sql_contains"] = sql_contains
        sql_regex = str(match.get("sql_regex") or "").strip()
        if sql_regex:
            try:
                re.compile(sql_regex)
            except re.error as exc:
                raise ConfigError(f"diagnostics rule sql_regex is invalid ({path}): {exc}") from exc
            normalized_match["sql_regex"] = sql_regex
        statement_type_is = str(match.get("statement_type_is") or "").strip().upper()
        if statement_type_is:
            normalized_match["statement_type_is"] = statement_type_is
        dynamic_feature_has = str(match.get("dynamic_feature_has") or "").strip().upper()
        if dynamic_feature_has:
            normalized_match["dynamic_feature_has"] = dynamic_feature_has
        if not normalized_match:
            raise ConfigError(f"diagnostics rule match must define at least one supported matcher: {path}")

        action = raw_rule.get("action") or {}
        if not isinstance(action, dict):
            raise ConfigError(f"diagnostics rule action must be object when set: {path}")
        allowed_action_keys = {"suggestion_sql_template", "block_actionability"}
        unknown_action_keys = sorted(set(action.keys()) - allowed_action_keys)
        if unknown_action_keys:
            raise ConfigError(f"diagnostics rule action contains unsupported keys {unknown_action_keys}: {path}")
        suggestion_sql_template = str(action.get("suggestion_sql_template") or "").strip()
        block_actionability = bool(action.get("block_actionability", False))
        normalized_rules.append(
            {
                "rule_id": rule_id,
                "message": message,
                "default_severity": default_severity,
                "match": normalized_match,
                "action": {
                    "suggestion_sql_template": suggestion_sql_template or None,
                    "block_actionability": block_actionability,
                },
            }
        )
    return normalized_rules


def normalize_diagnostics_config(diagnostics_cfg: dict[str, Any], *, config_path: Path) -> None:
    diagnostics_cfg.setdefault("rulepacks", [{"builtin": "core"}, {"builtin": "performance"}])
    rulepacks = diagnostics_cfg.get("rulepacks")
    if not isinstance(rulepacks, list):
        raise ConfigError("diagnostics.rulepacks must be array")

    normalized_rulepacks: list[dict[str, str]] = []
    loaded_rulepacks: list[dict[str, Any]] = []
    for entry in rulepacks:
        if not isinstance(entry, dict):
            raise ConfigError("diagnostics.rulepacks entries must be objects")
        builtin = str(entry.get("builtin") or "").strip().lower()
        file_ref = str(entry.get("file") or "").strip()
        if builtin:
            if builtin not in {"core", "performance"}:
                raise ConfigError("diagnostics.rulepacks builtin must be one of: core, performance")
            normalized_rulepacks.append({"builtin": builtin})
            continue
        if file_ref:
            file_path = Path(file_ref)
            if not file_path.is_absolute():
                file_path = (config_path.parent / file_path).resolve()
            if not file_path.exists():
                raise ConfigError(f"diagnostics rule file not found: {file_path}")
            normalized_rulepacks.append({"file": str(file_path)})
            loaded_rulepacks.append(
                {
                    "file": str(file_path),
                    "rules": _load_diagnostics_rule_file(file_path),
                }
            )
            continue
        raise ConfigError("diagnostics.rulepacks entries must set either builtin or file")
    diagnostics_cfg["rulepacks"] = normalized_rulepacks
    diagnostics_cfg["loaded_rulepacks"] = loaded_rulepacks

    diagnostics_cfg.setdefault("severity_overrides", {})
    severity_overrides = diagnostics_cfg.get("severity_overrides")
    if not isinstance(severity_overrides, dict):
        raise ConfigError("diagnostics.severity_overrides must be object")
    normalized_overrides: dict[str, str] = {}
    for rule_id, severity in severity_overrides.items():
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ConfigError("diagnostics.severity_overrides keys must be non-empty strings")
        normalized_severity = str(severity or "").strip().lower()
        if normalized_severity not in {"info", "warn", "error"}:
            raise ConfigError("diagnostics.severity_overrides values must be one of: info, warn, error")
        normalized_overrides[rule_id.strip()] = normalized_severity
    diagnostics_cfg["severity_overrides"] = normalized_overrides

    diagnostics_cfg.setdefault("disabled_rules", [])
    disabled_rules = diagnostics_cfg.get("disabled_rules")
    if not isinstance(disabled_rules, list):
        raise ConfigError("diagnostics.disabled_rules must be array")
    normalized_disabled = []
    for rule_id in disabled_rules:
        rule = str(rule_id or "").strip()
        if not rule:
            raise ConfigError("diagnostics.disabled_rules entries must be non-empty strings")
        normalized_disabled.append(rule)
    diagnostics_cfg["disabled_rules"] = normalized_disabled

