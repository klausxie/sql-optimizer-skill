from __future__ import annotations

from pathlib import Path
from typing import Any

from .configuration.common import (
    LEGACY_DOTTED_KEYS,
    REMOVED_KEYS,
    check_snake_case as _check_snake_case,
    has_key as _has_key,
    load_raw as _load_raw,
    merge_dict as _merge_dict,
    required as _required,
)
from .configuration.defaults import apply_minimal_defaults
from .configuration.versioning import apply_config_version_migration as _apply_config_version_migration
from .constants import ROOT_KEYS
from .errors import ConfigError


_SECTION_ALLOWED_KEYS = {
    "project": {"root_path"},
    "scan": {"mapper_globs"},
    "db": {"platform", "dsn", "schema"},
    "llm": {
        "enabled",
        "provider",
        "timeout_ms",
        "opencode_model",
        "api_base",
        "api_key",
        "api_model",
        "api_timeout_ms",
        "api_headers",
    },
    "report": {"enabled"},
}


def _require_object(cfg: dict[str, Any], section: str) -> dict[str, Any]:
    value = cfg.get(section)
    if value is None:
        cfg[section] = {}
        return cfg[section]
    if not isinstance(value, dict):
        raise ConfigError(f"{section} must be object")
    return value


def _validate_section_keys(cfg: dict[str, Any]) -> None:
    for section, allowed in _SECTION_ALLOWED_KEYS.items():
        section_cfg = _require_object(cfg, section)
        unknown = sorted(set(section_cfg.keys()) - allowed)
        if unknown:
            dotted = [f"{section}.{key}" for key in unknown]
            raise ConfigError(f"config key removed and no longer supported: {dotted[0]}")


def _validate_types(cfg: dict[str, Any]) -> None:
    project_cfg = cfg["project"]
    if not isinstance(project_cfg.get("root_path"), str) or not str(project_cfg["root_path"]).strip():
        raise ConfigError("project.root_path must be non-empty string")

    scan_cfg = cfg["scan"]
    mapper_globs = scan_cfg.get("mapper_globs")
    if not isinstance(mapper_globs, list) or not mapper_globs or not all(isinstance(x, str) and x.strip() for x in mapper_globs):
        raise ConfigError("scan.mapper_globs must be non-empty string array")

    db_cfg = cfg["db"]
    platform = str(db_cfg.get("platform") or "").strip().lower()
    if platform not in {"postgresql", "mysql"}:
        raise ConfigError("v1 only supports db.platform in {postgresql, mysql}")
    dsn = db_cfg.get("dsn")
    if not isinstance(dsn, str) or not dsn.strip():
        raise ConfigError("db.dsn must be non-empty string")
    schema = db_cfg.get("schema")
    if schema is not None and (not isinstance(schema, str) or not schema.strip()):
        raise ConfigError("db.schema must be non-empty string when set")

    llm_cfg = cfg["llm"]
    enabled = llm_cfg.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise ConfigError("llm.enabled must be boolean")
    provider = str(llm_cfg.get("provider") or "").strip()
    allowed_providers = {"opencode_run", "opencode_builtin", "heuristic", "direct_openai_compatible"}
    if provider not in allowed_providers:
        raise ConfigError(f"llm.provider must be one of: {sorted(allowed_providers)}")
    timeout = llm_cfg.get("timeout_ms")
    if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
        raise ConfigError("llm.timeout_ms must be positive integer when set")

    if provider == "direct_openai_compatible":
        for key in ("api_base", "api_key", "api_model"):
            value = llm_cfg.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"llm.{key} is required when llm.provider=direct_openai_compatible")
        api_timeout = llm_cfg.get("api_timeout_ms")
        if api_timeout is not None and (not isinstance(api_timeout, int) or api_timeout <= 0):
            raise ConfigError("llm.api_timeout_ms must be positive integer when set")
        headers = llm_cfg.get("api_headers")
        if headers is not None:
            if not isinstance(headers, dict):
                raise ConfigError("llm.api_headers must be object when set")
            for key, value in headers.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ConfigError("llm.api_headers must be object<string,string>")

    report_cfg = _require_object(cfg, "report")
    if "enabled" in report_cfg and not isinstance(report_cfg.get("enabled"), bool):
        raise ConfigError("report.enabled must be boolean")


def load_config(config_path: Path, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _apply_config_version_migration(_load_raw(config_path))
    if cli_overrides:
        cfg = _merge_dict(cfg, cli_overrides)

    _check_snake_case(cfg)
    is_resolved_config = config_path.name == "config.resolved.json"
    if not is_resolved_config:
        for dotted in sorted(LEGACY_DOTTED_KEYS):
            if _has_key(cfg, dotted):
                raise ConfigError(f"legacy config key not supported: {dotted}")
        for dotted in sorted(REMOVED_KEYS):
            if _has_key(cfg, dotted):
                raise ConfigError(f"config key removed and no longer supported: {dotted}")

        unknown = sorted(set(cfg.keys()) - ROOT_KEYS)
        if unknown:
            raise ConfigError(f"unknown root keys: {unknown}")

        _validate_section_keys(cfg)

    for key in ("project.root_path", "scan.mapper_globs", "db.platform", "db.dsn", "llm.provider"):
        _required(cfg, key)

    _validate_types(cfg)
    apply_minimal_defaults(cfg, config_path=config_path)
    return cfg
