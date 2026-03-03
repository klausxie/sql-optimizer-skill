from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .constants import ROOT_KEYS, RUNTIME_PROFILE_DEFAULTS
from .errors import ConfigError

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
LEGACY_DOTTED_KEYS = {
    "project.root",
    "db.type",
    "runtime.scan_timeout_ms",
    "runtime.optimize_timeout_ms",
    "runtime.validate_timeout_ms",
    "runtime.apply_timeout_ms",
    "runtime.report_timeout_ms",
    "runtime.scan_retry_max",
    "runtime.optimize_retry_max",
    "runtime.validate_retry_max",
    "runtime.apply_retry_max",
    "runtime.report_retry_max",
}
REMOVED_KEYS = {
    "validate.sample_count",
    "validate.min_sample_rows_for_hash",
    "validate.db_unreachable_high_rate_threshold",
    "validate.key_columns",
    "validate.compare_columns",
    "llm.executor",
    "llm.strict_required",
}


def _check_snake_case(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            # Allow arbitrary HTTP header keys under llm.api_headers.
            if path.endswith("llm.api_headers."):
                _check_snake_case(v, path + k + ".")
                continue
            # Allow rule-id keyed overrides under diagnostics.severity_overrides.
            if path.endswith("diagnostics.severity_overrides."):
                _check_snake_case(v, path + k + ".")
                continue
            if not SNAKE_CASE_RE.match(k):
                raise ConfigError(f"config key not snake_case: {path + k}")
            _check_snake_case(v, path + k + ".")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_snake_case(item, f"{path}[{i}].")


def _load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yml", ".yaml"}:
        if yaml is None:
            raise ConfigError("pyyaml is required for yaml config")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ConfigError("config must be object")
    return data


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _required(config: dict[str, Any], dotted: str) -> None:
    node: Any = config
    for k in dotted.split("."):
        if not isinstance(node, dict) or k not in node:
            raise ConfigError(f"missing required config: {dotted}")
        node = node[k]


def _has_key(config: dict[str, Any], dotted: str) -> bool:
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _load_diagnostics_rule_file(path: Path) -> list[dict[str, Any]]:
    data = _load_raw(path)
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


def load_config(config_path: Path, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _load_raw(config_path)
    unknown = sorted(set(cfg.keys()) - ROOT_KEYS)
    if unknown:
        raise ConfigError(f"unknown root keys: {unknown}")
    _check_snake_case(cfg)
    for dotted in sorted(LEGACY_DOTTED_KEYS):
        if _has_key(cfg, dotted):
            raise ConfigError(f"legacy config key not supported: {dotted}")
    for dotted in sorted(REMOVED_KEYS):
        if _has_key(cfg, dotted):
            raise ConfigError(f"config key removed and no longer supported: {dotted}")

    runtime = cfg.setdefault("runtime", {})
    profile = runtime.get("profile", "balanced")
    if profile not in RUNTIME_PROFILE_DEFAULTS:
        raise ConfigError(f"invalid runtime.profile: {profile}")
    runtime = _merge_dict(RUNTIME_PROFILE_DEFAULTS[profile], runtime)
    cfg["runtime"] = runtime

    if cli_overrides:
        cfg = _merge_dict(cfg, cli_overrides)

    project_cfg = cfg.setdefault("project", {})
    root_path = project_cfg.get("root_path")
    if isinstance(root_path, str) and root_path:
        p = Path(root_path)
        if not p.is_absolute():
            project_cfg["root_path"] = str((config_path.parent / p).resolve())

    apply_cfg = cfg.setdefault("apply", {})
    apply_cfg.setdefault("mode", "PATCH_ONLY")
    policy_cfg = cfg.setdefault("policy", {})
    policy_cfg.setdefault("require_perf_improvement", False)
    policy_cfg.setdefault("cost_threshold_pct", 0)
    policy_cfg.setdefault("allow_seq_scan_if_rows_below", 0)
    policy_cfg.setdefault("semantic_strict_mode", True)
    db_cfg = cfg.setdefault("db", {})
    db_cfg.setdefault("dsn", None)
    db_cfg.setdefault("schema", None)
    db_cfg.setdefault("statement_timeout_ms", 3000)
    db_cfg.setdefault("allow_explain_analyze", False)

    scan_cfg = cfg.setdefault("scan", {})
    scan_cfg.setdefault("mapper_globs", ["**/*Mapper.xml", "**/*.xml"])
    class_resolution_cfg = scan_cfg.setdefault("class_resolution", {})
    class_resolution_cfg.setdefault("mode", "tolerant")
    class_resolution_cfg.setdefault("enable_classpath_probe", True)
    class_resolution_cfg.setdefault("enable_type_sanitize", True)
    class_resolution_cfg.setdefault("statement_level_recovery", True)
    class_resolution_cfg.setdefault("min_success_ratio", 0.9)

    validate_cfg = cfg.setdefault("validate", {})
    validate_cfg.setdefault("db_reachable", False)
    validate_cfg.setdefault("plan_compare_enabled", True)
    validate_cfg.setdefault("allow_db_unreachable_fallback", True)
    validate_cfg.setdefault("validation_profile", "balanced")
    validate_cfg.setdefault("selection_mode", "patchability_first")
    validate_cfg.setdefault("require_semantic_match", True)
    validate_cfg.setdefault("require_perf_evidence_for_pass", False)
    validate_cfg.setdefault("require_verified_evidence_for_pass", False)
    validate_cfg.setdefault("delivery_bias", "conservative")
    if str(validate_cfg.get("validation_profile", "balanced")) not in {"strict", "balanced", "relaxed"}:
        raise ConfigError("validate.validation_profile must be one of: strict, balanced, relaxed")
    if str(validate_cfg.get("selection_mode", "patchability_first")).strip().lower() not in {"patchability_first"}:
        raise ConfigError("validate.selection_mode must be one of: patchability_first")
    for key in ("require_semantic_match", "require_perf_evidence_for_pass", "require_verified_evidence_for_pass"):
        if not isinstance(validate_cfg.get(key), bool):
            raise ConfigError(f"validate.{key} must be boolean")
    if str(validate_cfg.get("delivery_bias", "conservative")).strip().lower() not in {"conservative"}:
        raise ConfigError("validate.delivery_bias must be one of: conservative")

    llm_cfg = cfg.setdefault("llm", {})
    llm_cfg.setdefault("enabled", False)
    llm_cfg.setdefault("provider", "opencode_builtin")
    llm_cfg.setdefault("timeout_ms", 15000)
    llm_cfg.setdefault("opencode_model", None)
    llm_cfg.setdefault("api_base", None)
    llm_cfg.setdefault("api_key", None)
    llm_cfg.setdefault("api_model", None)
    llm_cfg.setdefault("api_timeout_ms", None)
    llm_cfg.setdefault("api_headers", None)
    provider = str(llm_cfg.get("provider", "opencode_builtin"))
    allowed_providers = {"opencode_run", "opencode_builtin", "heuristic", "direct_openai_compatible"}
    if provider not in allowed_providers:
        raise ConfigError(f"llm.provider must be one of: {sorted(allowed_providers)}")
    if provider == "direct_openai_compatible":
        for key in ("api_base", "api_key", "api_model"):
            value = llm_cfg.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"llm.{key} is required when llm.provider=direct_openai_compatible")
        timeout = llm_cfg.get("api_timeout_ms")
        if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
            raise ConfigError("llm.api_timeout_ms must be positive integer when set")
        headers = llm_cfg.get("api_headers")
        if headers is not None:
            if not isinstance(headers, dict):
                raise ConfigError("llm.api_headers must be object when set")
            for k, v in headers.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    raise ConfigError("llm.api_headers must be object<string,string>")
    report_cfg = cfg.setdefault("report", {})
    report_cfg.setdefault("enabled", True)
    if not isinstance(report_cfg.get("enabled"), bool):
        raise ConfigError("report.enabled must be boolean")

    diagnostics_cfg = cfg.setdefault("diagnostics", {})
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

    verification_cfg = cfg.setdefault("verification", {})
    verification_cfg.setdefault("enforce_verified_outputs", False)
    if not isinstance(verification_cfg.get("enforce_verified_outputs"), bool):
        raise ConfigError("verification.enforce_verified_outputs must be boolean")
    verification_cfg.setdefault("critical_output_policy", None)
    critical_output_policy = verification_cfg.get("critical_output_policy")
    if critical_output_policy is not None:
        critical_output_policy = str(critical_output_policy).strip().lower()
        if critical_output_policy not in {"warn", "block"}:
            raise ConfigError("verification.critical_output_policy must be one of: warn, block")
        verification_cfg["critical_output_policy"] = critical_output_policy

    for key in [
        "project.root_path",
        "scan.mapper_globs",
        "db.platform",
        "policy.require_perf_improvement",
        "policy.cost_threshold_pct",
        "policy.allow_seq_scan_if_rows_below",
        "policy.semantic_strict_mode",
        "runtime.stage_timeout_ms.scan",
        "runtime.stage_timeout_ms.optimize",
        "runtime.stage_timeout_ms.validate",
        "runtime.stage_timeout_ms.apply",
        "runtime.stage_timeout_ms.report",
        "runtime.stage_timeout_ms.preflight",
        "runtime.stage_retry_max.preflight",
        "runtime.stage_retry_max.scan",
        "runtime.stage_retry_max.optimize",
        "runtime.stage_retry_max.validate",
        "runtime.stage_retry_max.apply",
        "runtime.stage_retry_max.report",
        "runtime.stage_retry_backoff_ms",
    ]:
        _required(cfg, key)
    cfg["config_version"] = cfg.get("config_version", "v1")

    platform = cfg["db"]["platform"]
    if platform != "postgresql":
        raise ConfigError("v1 only supports db.platform=postgresql")
    return cfg
