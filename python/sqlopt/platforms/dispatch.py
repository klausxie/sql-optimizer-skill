from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import StageError


def platform_key(config: dict[str, Any]) -> str:
    return str((config.get("db", {}) or {}).get("platform", "")).strip().lower()


def _registry():
    from .postgresql import adapter as postgresql

    return {"postgresql": postgresql}


def _resolve_platform_module(config: dict[str, Any]):
    platform = platform_key(config)
    mod = _registry().get(platform)
    if mod is not None:
        return mod
    raise StageError(f"unsupported db.platform: {platform or '<empty>'}", reason_code="UNSUPPORTED_PLATFORM")


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    mod = _resolve_platform_module(config)
    return mod.check_db_connectivity(config)


def collect_sql_evidence(config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
    mod = _resolve_platform_module(config)
    return mod.collect_sql_evidence(config, sql)


def compare_plan(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    mod = _resolve_platform_module(config)
    return mod.compare_plan(config, original_sql, rewritten_sql, evidence_dir)


def compare_semantics(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    mod = _resolve_platform_module(config)
    return mod.compare_semantics(config, original_sql, rewritten_sql, evidence_dir)
