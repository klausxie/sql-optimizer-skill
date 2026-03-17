"""
Shared Config Module

Centralized configuration loading and validation.
Re-exports from core config module.
"""

from pathlib import Path
from typing import Any

from sqlopt.config import load_config as _load_config


def load_config(
    config_path: Path | str, cli_overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Load and validate configuration from file.

    Args:
        config_path: Path to configuration file
        cli_overrides: Optional CLI overrides to merge

    Returns:
        Validated and resolved configuration dictionary

    Raises:
        ConfigError: If configuration is invalid
    """
    if isinstance(config_path, str):
        config_path = Path(config_path)
    return _load_config(config_path, cli_overrides)


def get_default_config() -> dict[str, Any]:
    """Get default configuration.

    Returns:
        Default configuration dictionary
    """
    return {
        "config_version": "v1",
        "project": {
            "root_path": ".",
        },
        "scan": {
            "mapper_globs": ["**/*.xml"],
        },
        "db": {
            "platform": "postgresql",
            "dsn": "",
        },
        "llm": {
            "enabled": True,
            "provider": "opencode_run",
        },
    }


__all__ = [
    "load_config",
    "get_default_config",
]
