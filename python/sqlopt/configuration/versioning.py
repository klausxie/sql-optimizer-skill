from __future__ import annotations

from typing import Any, Callable

from ..errors import ConfigError

ConfigMigrator = Callable[[dict[str, Any]], dict[str, Any]]

CONFIG_VERSION_CURRENT = "v1"
CONFIG_VERSION_ALIASES = {
    "1": "v1",
    "1.0": "v1",
}
CONFIG_VERSION_MIGRATORS: dict[str, ConfigMigrator] = {
    "v1": lambda cfg: cfg,
}


def normalize_config_version(value: Any) -> str:
    raw = str(value or CONFIG_VERSION_CURRENT).strip().lower()
    normalized = CONFIG_VERSION_ALIASES.get(raw, raw)
    if normalized not in CONFIG_VERSION_MIGRATORS:
        supported = ", ".join(sorted(CONFIG_VERSION_MIGRATORS.keys()))
        raise ConfigError(f"unsupported config_version: {value!r}, supported: {supported}")
    return normalized


def apply_config_version_migration(cfg: dict[str, Any]) -> dict[str, Any]:
    version = normalize_config_version(cfg.get("config_version"))
    migrated = CONFIG_VERSION_MIGRATORS[version](dict(cfg))
    if not isinstance(migrated, dict):
        raise ConfigError(f"config migrator for {version} must return object")
    migrated["config_version"] = version
    return migrated

