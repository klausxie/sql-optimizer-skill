from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import StageError
from .base import FunctionPlatformAdapter, PlatformAdapter, PlatformCapabilities


def platform_key(config: dict[str, Any]) -> str:
    return str((config.get("db", {}) or {}).get("platform", "")).strip().lower()


def _registry():
    from .mysql import adapter as mysql
    from .postgresql import adapter as postgresql
    from .h2 import adapter as h2

    return {
        "postgresql": postgresql.get_adapter(), 
        "mysql": mysql.get_adapter(),
        "h2": h2.get_adapter(),
    }


def _is_adapter_like(entry: Any) -> bool:
    return (
        hasattr(entry, "capabilities")
        and callable(getattr(entry, "check_db_connectivity", None))
        and callable(getattr(entry, "collect_sql_evidence", None))
        and callable(getattr(entry, "compare_plan", None))
        and callable(getattr(entry, "compare_semantics", None))
    )


def _is_legacy_module_like(entry: Any) -> bool:
    return (
        callable(getattr(entry, "check_db_connectivity", None))
        and callable(getattr(entry, "collect_sql_evidence", None))
        and callable(getattr(entry, "compare_plan", None))
        and callable(getattr(entry, "compare_semantics", None))
    )


def _coerce_registry_entry(platform: str, entry: Any) -> PlatformAdapter:
    if _is_adapter_like(entry):
        return entry
    get_adapter = getattr(entry, "get_adapter", None)
    if callable(get_adapter):
        adapter = get_adapter()
        if _is_adapter_like(adapter):
            return adapter
    if _is_legacy_module_like(entry):
        return FunctionPlatformAdapter(
            name=platform,
            capabilities=PlatformCapabilities(),
            check_db_connectivity_fn=entry.check_db_connectivity,
            collect_sql_evidence_fn=entry.collect_sql_evidence,
            compare_plan_fn=entry.compare_plan,
            compare_semantics_fn=entry.compare_semantics,
        )
    raise StageError(f"invalid platform adapter registration: {platform}", reason_code="INVALID_PLATFORM_ADAPTER")


def get_platform_adapter(config: dict[str, Any]) -> PlatformAdapter:
    platform = platform_key(config)
    entry = _registry().get(platform)
    if entry is not None:
        return _coerce_registry_entry(platform, entry)
    raise StageError(f"unsupported db.platform: {platform or '<empty>'}", reason_code="UNSUPPORTED_PLATFORM")


def get_platform_capabilities(config: dict[str, Any]) -> PlatformCapabilities:
    adapter = get_platform_adapter(config)
    return adapter.capabilities


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    adapter = get_platform_adapter(config)
    return adapter.check_db_connectivity(config)


def collect_sql_evidence(config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = get_platform_adapter(config)
    return adapter.collect_sql_evidence(config, sql)


def compare_plan(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    adapter = get_platform_adapter(config)
    return adapter.compare_plan(config, original_sql, rewritten_sql, evidence_dir)


def compare_semantics(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    adapter = get_platform_adapter(config)
    return adapter.compare_semantics(config, original_sql, rewritten_sql, evidence_dir)
