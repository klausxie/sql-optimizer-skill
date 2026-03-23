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
    "scan": {"mapper_globs", "statement_types"},
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


def _mask_sensitive_value(value: str, max_length: int = 50) -> str:
    """Mask sensitive information in values for display."""
    if not isinstance(value, str):
        return str(value)
    # Mask password-like patterns
    import re

    # Match patterns like user:pass@ or password=xxx
    masked = re.sub(r"([:@/])([^:/@]+)([@/])", r"\1****\3", value)
    if len(masked) > max_length:
        masked = masked[:max_length] + "..."
    return masked


def _format_actual_value(value: Any) -> str:
    """Format actual value for error messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"boolean ({value})"
    if isinstance(value, int):
        return f"integer ({value})"
    if isinstance(value, float):
        return f"float ({value})"
    if isinstance(value, str):
        if len(value) > 30:
            return f"string (len={len(value)}, first 30: '{value[:30]}...')"
        return f"string ('{value}')"
    if isinstance(value, list):
        return f"list (len={len(value)}, first: {_format_actual_value(value[0]) if value else 'empty'})"
    if isinstance(value, dict):
        keys = list(value.keys())[:3]
        return f"dict (keys: {keys}{'...' if len(value) > 3 else ''})"
    return str(type(value).__name__)


class ValidationErrorCollector:
    """Collects all validation errors instead of failing on first one."""

    def __init__(self):
        self.errors: list[str] = []

    def add(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def raise_if_any(self) -> None:
        """Raise ConfigError with all collected errors."""
        if self.errors:
            if len(self.errors) == 1:
                raise ConfigError(self.errors[0])
            # Format multiple errors clearly
            error_msg = f"Found {len(self.errors)} validation errors:\n"
            for i, err in enumerate(self.errors, 1):
                error_msg += f"  {i}. {err}\n"
            raise ConfigError(error_msg.strip())


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
        raise ConfigError(
            f"{section} must be object, got: {_format_actual_value(value)}"
        )
    return value


def validate_section_keys(cfg: dict[str, Any]) -> list[str]:
    """Validate that config sections only contain allowed keys.

    Args:
        cfg: Configuration dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []
    for section, allowed in SECTION_ALLOWED_KEYS.items():
        section_cfg = _require_object(cfg, section)
        unknown = sorted(set(section_cfg.keys()) - allowed)
        if unknown:
            for key in unknown:
                errors.append(
                    f"config key '{section}.{key}' is not supported. "
                    f"Allowed keys in '{section}': {sorted(allowed)}"
                )
    return errors


def validate_types(cfg: dict[str, Any]) -> list[str]:
    """Validate configuration value types and constraints.

    Args:
        cfg: Configuration dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Validate project section
    project_cfg = cfg.get("project", {})
    root_path = project_cfg.get("root_path")
    if not isinstance(root_path, str) or not str(root_path).strip():
        errors.append(
            f"project.root_path must be non-empty string, got: {_format_actual_value(root_path)}"
        )

    # Validate scan section
    scan_cfg = cfg.get("scan", {})
    mapper_globs = scan_cfg.get("mapper_globs")
    if not isinstance(mapper_globs, list) or not mapper_globs:
        errors.append(
            f"scan.mapper_globs must be non-empty array, got: {_format_actual_value(mapper_globs)}"
        )
    elif not all(isinstance(x, str) and x.strip() for x in mapper_globs):
        invalid_items = [
            x for x in mapper_globs if not isinstance(x, str) or not x.strip()
        ]
        errors.append(
            f"scan.mapper_globs must contain non-empty strings, found: {invalid_items}"
        )

    # Validate scan.statement_types
    statement_types = scan_cfg.get("statement_types")
    if statement_types is not None:
        if not isinstance(statement_types, list):
            errors.append(
                f"scan.statement_types must be array, got: {_format_actual_value(statement_types)}"
            )
        else:
            valid_types = {"select", "insert", "update", "delete"}
            for item in statement_types:
                if not isinstance(item, str):
                    errors.append(
                        f"scan.statement_types elements must be strings, got: {_format_actual_value(item)}"
                    )
                elif item.lower().strip() not in valid_types:
                    errors.append(
                        f"scan.statement_types value '{item}' is invalid. Must be one of: {sorted(valid_types)}"
                    )

    # Validate db section
    db_cfg = cfg.get("db", {})
    platform = str(db_cfg.get("platform") or "").strip().lower()
    if platform not in {"postgresql", "mysql"}:
        errors.append(
            f"db.platform must be one of {{postgresql, mysql}}, got: '{platform}'"
        )
    dsn = db_cfg.get("dsn")
    # DSN can be empty/placeholder - will run in degraded (static-only) mode
    if dsn is not None and dsn != "":
        if not isinstance(dsn, str):
            errors.append(f"db.dsn must be string, got: {_format_actual_value(dsn)}")
    schema = db_cfg.get("schema")
    if schema is not None and (not isinstance(schema, str) or not schema.strip()):
        errors.append(
            f"db.schema must be non-empty string when set, got: {_format_actual_value(schema)}"
        )

    # Validate llm section
    llm_cfg = cfg.get("llm", {})
    enabled = llm_cfg.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append(
            f"llm.enabled must be boolean, got: {_format_actual_value(enabled)}"
        )
    provider = str(llm_cfg.get("provider") or "").strip()
    allowed_providers = {
        "opencode_run",
        "opencode_builtin",
        "heuristic",
        "direct_openai_compatible",
    }
    if provider not in allowed_providers:
        errors.append(
            f"llm.provider must be one of: {sorted(allowed_providers)}, got: '{provider}'"
        )
    timeout = llm_cfg.get("timeout_ms")
    if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
        errors.append(
            f"llm.timeout_ms must be positive integer, got: {_format_actual_value(timeout)}"
        )

    # Validate direct_openai_compatible specific settings
    if provider == "direct_openai_compatible":
        for key in ("api_base", "api_key", "api_model"):
            value = llm_cfg.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"llm.{key} is required when llm.provider=direct_openai_compatible, "
                    f"got: {_format_actual_value(value)}"
                )
        api_timeout = llm_cfg.get("api_timeout_ms")
        if api_timeout is not None and (
            not isinstance(api_timeout, int) or api_timeout <= 0
        ):
            errors.append(
                f"llm.api_timeout_ms must be positive integer, got: {_format_actual_value(api_timeout)}"
            )
        headers = llm_cfg.get("api_headers")
        if headers is not None:
            if not isinstance(headers, dict):
                errors.append(
                    f"llm.api_headers must be object, got: {_format_actual_value(headers)}"
                )
            else:
                for key, value in headers.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        errors.append(
                            f"llm.api_headers values must be strings, got key: {_format_actual_value(key)}, "
                            f"value: {_format_actual_value(value)}"
                        )

    # Validate report section
    report_cfg = cfg.get("report", {})
    if "enabled" in report_cfg and not isinstance(report_cfg.get("enabled"), bool):
        errors.append(
            f"report.enabled must be boolean, got: {_format_actual_value(report_cfg.get('enabled'))}"
        )

    # Validate rules section (if present)
    if "rules" in cfg:
        rules_cfg = cfg["rules"]
        if not isinstance(rules_cfg, dict):
            errors.append(
                f"rules must be object, got: {_format_actual_value(rules_cfg)}"
            )
        else:
            if "enabled" in rules_cfg and not isinstance(
                rules_cfg.get("enabled"), bool
            ):
                errors.append(
                    f"rules.enabled must be boolean, got: {_format_actual_value(rules_cfg.get('enabled'))}"
                )
            if "custom_rules_path" in rules_cfg:
                path = rules_cfg.get("custom_rules_path")
                if path is not None and not isinstance(path, str):
                    errors.append(
                        f"rules.custom_rules_path must be string or null, "
                        f"got: {_format_actual_value(path)}"
                    )
            if "custom_rules" in rules_cfg:
                rules_list = rules_cfg.get("custom_rules")
                if not isinstance(rules_list, list):
                    errors.append(
                        f"rules.custom_rules must be array, got: {_format_actual_value(rules_list)}"
                    )
            if "builtin_rules" in rules_cfg:
                builtin = rules_cfg.get("builtin_rules")
                if not isinstance(builtin, dict):
                    errors.append(
                        f"rules.builtin_rules must be object, got: {_format_actual_value(builtin)}"
                    )

    # Validate prompt_injections section (if present)
    if "prompt_injections" in cfg:
        prompt_cfg = cfg["prompt_injections"]
        if not isinstance(prompt_cfg, dict):
            errors.append(
                f"prompt_injections must be object, got: {_format_actual_value(prompt_cfg)}"
            )
        else:
            if "system" in prompt_cfg:
                system = prompt_cfg.get("system")
                if not isinstance(system, list):
                    errors.append(
                        f"prompt_injections.system must be array, got: {_format_actual_value(system)}"
                    )
            if "by_rule" in prompt_cfg:
                by_rule = prompt_cfg.get("by_rule")
                if not isinstance(by_rule, list):
                    errors.append(
                        f"prompt_injections.by_rule must be array, got: {_format_actual_value(by_rule)}"
                    )

    return errors


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
    collector = ValidationErrorCollector()

    # Check for legacy keys
    for dotted in sorted(LEGACY_DOTTED_KEYS):
        if _has_key(cfg, dotted):
            collector.add(f"legacy config key not supported: {dotted}")

    # Strip known removed keys for backward compatibility.
    # These keys are now auto-injected internally by defaults.
    strip_removed_keys(cfg)

    # Check for unknown root keys
    unknown = sorted(set(cfg.keys()) - ROOT_KEYS)
    if unknown:
        collector.add(f"unknown root keys: {unknown}")

    # Validate section keys
    section_errors = validate_section_keys(cfg)
    for error in section_errors:
        collector.add(error)

    # Validate types
    type_errors = validate_types(cfg)
    for error in type_errors:
        collector.add(error)

    # Raise all collected errors
    collector.raise_if_any()


def validate_resolved_config(cfg: dict[str, Any]) -> None:
    """Validate resolved configuration (with internal defaults applied).

    This validates the full configuration after internal defaults have been
    applied, checking only types and constraints (not key restrictions).

    Args:
        cfg: Resolved configuration dictionary

    Raises:
        ConfigError: If validation fails
    """
    collector = ValidationErrorCollector()

    # For resolved config, only validate types
    type_errors = validate_types(cfg)
    for error in type_errors:
        collector.add(error)

    collector.raise_if_any()
