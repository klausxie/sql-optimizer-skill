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

# Root sections that are auto-injected internally (silently ignored if present)
AUTO_INJECTED_SECTIONS = {
    "validate",
    "policy",
    "apply",
    "patch",
    "diagnostics",
    "runtime",
    "verification",
    "rules",
    "prompt_injections",
}


def check_snake_case(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            # Allow arbitrary HTTP header keys under llm.api_headers.
            if path.endswith("llm.api_headers."):
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


def strip_auto_injected_sections(config: dict[str, Any]) -> list[str]:
    """Remove auto-injected sections from user config.

    These sections are managed internally and should not be in user config.
    They are silently ignored for backward compatibility.

    Args:
        config: Configuration dictionary

    Returns:
        List of removed section names
    """
    removed = []
    for section in AUTO_INJECTED_SECTIONS:
        if section in config:
            del config[section]
            removed.append(section)
    return removed
