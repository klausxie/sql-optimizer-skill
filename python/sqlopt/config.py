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
    if str(validate_cfg.get("validation_profile", "balanced")) not in {"strict", "balanced", "relaxed"}:
        raise ConfigError("validate.validation_profile must be one of: strict, balanced, relaxed")

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
