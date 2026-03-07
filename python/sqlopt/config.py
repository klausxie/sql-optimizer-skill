from __future__ import annotations

from pathlib import Path
from typing import Any

from .configuration.common import (
    check_snake_case as _check_snake_case,
    load_raw as _load_raw,
    merge_dict as _merge_dict,
    required as _required,
)
from .configuration.defaults import apply_minimal_defaults
from .configuration.validation import validate_resolved_config, validate_user_config
from .configuration.versioning import apply_config_version_migration as _apply_config_version_migration


def load_config(config_path: Path, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load and validate configuration from file.

    Args:
        config_path: Path to configuration file
        cli_overrides: Optional CLI overrides to merge

    Returns:
        Validated and resolved configuration dictionary

    Raises:
        ConfigError: If configuration is invalid
    """
    cfg = _apply_config_version_migration(_load_raw(config_path))
    if cli_overrides:
        cfg = _merge_dict(cfg, cli_overrides)

    _check_snake_case(cfg)
    is_resolved_config = config_path.name == "config.resolved.json"

    if not is_resolved_config:
        # Validate user-facing configuration
        validate_user_config(cfg)
    else:
        # Validate resolved configuration
        validate_resolved_config(cfg)

    # Check required fields
    for key in ("project.root_path", "scan.mapper_globs", "db.platform", "db.dsn", "llm.provider"):
        _required(cfg, key)

    apply_minimal_defaults(cfg, config_path=config_path)
    return cfg
