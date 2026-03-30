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
    has_key as _has_key,
    strip_removed_keys,
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

    # Strip known removed keys for backward compatibility.
    # These keys are now auto-injected internally by defaults.
    strip_removed_keys(cfg)

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
