from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..errors import ConfigError

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

# Removed keys with migration hints
REMOVED_KEYS_WITH_HINTS = {
    # Root sections - now auto-injected internally
    "validate": "This section is now auto-injected internally. Remove it from your config file.",
    "policy": "This section is now auto-injected internally. Remove it from your config file.",
    "apply": "This section is now auto-injected internally. Remove it from your config file.",
    "patch": "This section is now auto-injected internally. Remove it from your config file.",
    "diagnostics": "This section is now auto-injected internally. Remove it from your config file.",
    "runtime": "This section is now auto-injected internally. Remove it from your config file.",
    "verification": "This section is now auto-injected internally. Remove it from your config file.",
    # Validate section keys
    "validate.sample_count": "Validation settings are now managed internally. Remove this key.",
    "validate.min_sample_rows_for_hash": "Validation settings are now managed internally. Remove this key.",
    "validate.db_unreachable_high_rate_threshold": "Validation settings are now managed internally. Remove this key.",
    "validate.key_columns": "Validation settings are now managed internally. Remove this key.",
    "validate.compare_columns": "Validation settings are now managed internally. Remove this key.",
    # Scan section keys
    "scan.max_variants_per_statement": "Scanner settings are now managed internally. Remove this key.",
    "scan.java_scanner": "Scanner configuration is now managed internally. Remove this key.",
    "scan.class_resolution": "Scanner configuration is now managed internally. Remove this key.",
    "scan.enable_fragment_catalog": "Fragment catalog is now managed internally. Remove this key.",
    # Database section keys
    "db.statement_timeout_ms": "Database timeout settings are now managed internally. Remove this key.",
    "db.allow_explain_analyze": "EXPLAIN ANALYZE settings are now managed internally. Remove this key.",
    # LLM section keys
    "llm.retry": "LLM retry is always enabled. Remove this key.",
    "llm.output_validation": "LLM output validation is always enabled. Remove this key.",
    "llm.executor": "LLM executor settings are now managed internally. Remove this key.",
    "llm.strict_required": "LLM strict mode is now managed internally. Remove this key.",
}

# Backward compatibility: keep REMOVED_KEYS as a set for existing code
REMOVED_KEYS = set(REMOVED_KEYS_WITH_HINTS.keys())


def check_snake_case(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            # Allow arbitrary HTTP header keys under llm.api_headers.
            if path.endswith("llm.api_headers."):
                check_snake_case(value, path + key + ".")
                continue
            # Allow rule-id keyed overrides under diagnostics.severity_overrides.
            if path.endswith("diagnostics.severity_overrides."):
                check_snake_case(value, path + key + ".")
                continue
            # Allow rule IDs (uppercase) under rules.builtin_rules.
            if path.endswith("rules.builtin_rules."):
                check_snake_case(value, path + key + ".")
                continue
            if not SNAKE_CASE_RE.match(key):
                raise ConfigError(f"config key not snake_case: {path + key}")
            check_snake_case(value, path + key + ".")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            check_snake_case(item, f"{path}[{i}].")


def load_raw(path: Path) -> dict[str, Any]:
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


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def required(config: dict[str, Any], dotted: str) -> None:
    node: Any = config
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise ConfigError(f"missing required config: {dotted}")
        node = node[key]


def has_key(config: dict[str, Any], dotted: str) -> bool:
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def remove_key(config: dict[str, Any], dotted: str) -> bool:
    """Remove a dotted key from config if it exists.

    Args:
        config: Configuration dictionary
        dotted: Dotted key path, e.g. "scan.java_scanner"

    Returns:
        True if key existed and was removed, False otherwise
    """
    parts = dotted.split(".")
    if not parts:
        return False
    node: Any = config
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if not isinstance(node, dict):
        return False
    leaf = parts[-1]
    if leaf in node:
        del node[leaf]
        return True
    return False


def check_removed_keys(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Check for removed configuration keys and return warnings with hints.

    Args:
        config: Configuration dictionary to check

    Returns:
        List of tuples (key, hint) for each removed key found
    """
    warnings = []
    for dotted_key, hint in sorted(REMOVED_KEYS_WITH_HINTS.items()):
        if has_key(config, dotted_key):
            warnings.append((dotted_key, hint))
    return warnings


def strip_removed_keys(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Remove removed/deprecated keys from config and return what was stripped.

    This keeps backward compatibility with older configs by silently ignoring
    known removed keys.
    """
    removed = check_removed_keys(config)
    for dotted_key, _ in sorted(removed, key=lambda item: item[0].count("."), reverse=True):
        remove_key(config, dotted_key)
    return removed
