"""Configuration validation module.

This module centralizes all configuration validation logic, providing
clear separation between user-facing config validation and resolved
config validation.
"""

from __future__ import annotations

from typing import Any

from ..constants import ROOT_KEYS
from ..errors import ConfigError
from .common import (
    LEGACY_DOTTED_KEYS,
    REMOVED_KEYS_WITH_HINTS,
    check_removed_keys,
    has_key as _has_key,
)


# Allowed keys per section for user-facing configuration
SECTION_ALLOWED_KEYS = {
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
    # User-extensible sections (internal, but allowed in user config for migration)
    "rules": {"enabled", "custom_rules_path", "custom_rules", "builtin_rules"},
    "prompt_injections": {"system", "by_rule"},
}


def _require_object(cfg: dict[str, Any], section: str) -> dict[str, Any]:
    """Ensure a config section exists and is a dict object.

    Args:
        cfg: Configuration dictionary
        section: Section name to check

    Returns:
        The section dictionary (creates empty dict if missing)

    Raises:
        ConfigError: If section exists but is not a dict
    """
    value = cfg.get(section)
    if value is None:
        cfg[section] = {}
        return cfg[section]
    if not isinstance(value, dict):
        raise ConfigError(f"{section} must be object")
    return value


def validate_section_keys(cfg: dict[str, Any]) -> None:
    """Validate that config sections only contain allowed keys.

    Args:
        cfg: Configuration dictionary

    Raises:
        ConfigError: If unknown keys are found in any section
    """
    for section, allowed in SECTION_ALLOWED_KEYS.items():
        section_cfg = _require_object(cfg, section)
        unknown = sorted(set(section_cfg.keys()) - allowed)
        if unknown:
            dotted = [f"{section}.{key}" for key in unknown]
            raise ConfigError(f"config key removed and no longer supported: {dotted[0]}")


def validate_types(cfg: dict[str, Any]) -> None:
    """Validate configuration value types and constraints.

    Args:
        cfg: Configuration dictionary

    Raises:
        ConfigError: If any value has invalid type or violates constraints
    """
    # Validate project section
    project_cfg = cfg["project"]
    if not isinstance(project_cfg.get("root_path"), str) or not str(project_cfg["root_path"]).strip():
        raise ConfigError("project.root_path must be non-empty string")

    # Validate scan section
    scan_cfg = cfg["scan"]
    mapper_globs = scan_cfg.get("mapper_globs")
    if not isinstance(mapper_globs, list) or not mapper_globs or not all(isinstance(x, str) and x.strip() for x in mapper_globs):
        raise ConfigError("scan.mapper_globs must be non-empty string array")

    # Validate db section
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

    # Validate llm section
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

    # Validate direct_openai_compatible specific settings
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

    # Validate report section
    report_cfg = _require_object(cfg, "report")
    if "enabled" in report_cfg and not isinstance(report_cfg.get("enabled"), bool):
        raise ConfigError("report.enabled must be boolean")

    # Validate rules section (if present)
    if "rules" in cfg:
        rules_cfg = cfg["rules"]
        if not isinstance(rules_cfg, dict):
            raise ConfigError("rules must be object")
        if "enabled" in rules_cfg and not isinstance(rules_cfg.get("enabled"), bool):
            raise ConfigError("rules.enabled must be boolean")
        if "custom_rules_path" in rules_cfg:
            path = rules_cfg.get("custom_rules_path")
            if path is not None and not isinstance(path, str):
                raise ConfigError("rules.custom_rules_path must be string or null")
        if "custom_rules" in rules_cfg:
            rules_list = rules_cfg.get("custom_rules")
            if not isinstance(rules_list, list):
                raise ConfigError("rules.custom_rules must be array")
        if "builtin_rules" in rules_cfg:
            builtin = rules_cfg.get("builtin_rules")
            if not isinstance(builtin, dict):
                raise ConfigError("rules.builtin_rules must be object")

    # Validate prompt_injections section (if present)
    if "prompt_injections" in cfg:
        prompt_cfg = cfg["prompt_injections"]
        if not isinstance(prompt_cfg, dict):
            raise ConfigError("prompt_injections must be object")
        if "system" in prompt_cfg:
            system = prompt_cfg.get("system")
            if not isinstance(system, list):
                raise ConfigError("prompt_injections.system must be array")
        if "by_rule" in prompt_cfg:
            by_rule = prompt_cfg.get("by_rule")
            if not isinstance(by_rule, list):
                raise ConfigError("prompt_injections.by_rule must be array")


def validate_user_config(cfg: dict[str, Any]) -> None:
    """Validate user-facing configuration.

    This validates the configuration file provided by users, checking:
    - No legacy or removed keys
    - Only known root keys
    - Section keys are allowed
    - Required fields are present
    - Types and constraints are valid

    Args:
        cfg: User configuration dictionary

    Raises:
        ConfigError: If validation fails
    """
    # Check for legacy keys
    for dotted in sorted(LEGACY_DOTTED_KEYS):
        if _has_key(cfg, dotted):
            raise ConfigError(f"legacy config key not supported: {dotted}")

    # Check for removed keys with helpful hints
    removed_warnings = check_removed_keys(cfg)
    if removed_warnings:
        # Format error message with hints
        key, hint = removed_warnings[0]  # Show first removed key
        error_msg = f"Config key '{key}' is no longer supported.\nHint: {hint}"
        if len(removed_warnings) > 1:
            error_msg += f"\n\nFound {len(removed_warnings)} removed key(s) in total. Please remove all of them."
        raise ConfigError(error_msg)

    # Check for unknown root keys
    unknown = sorted(set(cfg.keys()) - ROOT_KEYS)
    if unknown:
        raise ConfigError(f"unknown root keys: {unknown}")

    # Validate section keys
    validate_section_keys(cfg)

    # Validate types
    validate_types(cfg)


def validate_resolved_config(cfg: dict[str, Any]) -> None:
    """Validate resolved configuration (with internal defaults applied).

    This validates the full configuration after internal defaults have been
    applied, checking only types and constraints (not key restrictions).

    Args:
        cfg: Resolved configuration dictionary

    Raises:
        ConfigError: If validation fails
    """
    # For resolved config, only validate types
    validate_types(cfg)
