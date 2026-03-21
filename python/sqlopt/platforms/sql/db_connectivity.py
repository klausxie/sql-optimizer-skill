from __future__ import annotations

from typing import Any


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """Check database connectivity for MySQL or PostgreSQL platforms.

    Args:
        config: Dict with db.platform and db.dsn keys.

    Returns:
        Dict with ok, error, driver, and db_version fields.
    """
    platform = str((config.get("db", {}) or {}).get("platform", "")).strip().lower()

    if platform == "mysql":
        return _check_mysql_connectivity(config)
    elif platform == "postgresql":
        return _check_postgresql_connectivity(config)
    else:
        return {
            "ok": False,
            "error": f"unsupported platform: {platform}",
            "driver": None,
            "db_version": None,
        }


def _check_mysql_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """Check MySQL connectivity via mysql.evidence.check_db_connectivity."""
    try:
        from ..mysql.evidence import check_db_connectivity as mysql_check

        result = mysql_check(config)
        return _transform_result(result)
    except ImportError:
        return {
            "ok": False,
            "error": "mysql driver not installed",
            "driver": None,
            "db_version": None,
        }


def _check_postgresql_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """Check PostgreSQL connectivity via postgresql.evidence.check_db_connectivity."""
    try:
        from ..postgresql.evidence import check_db_connectivity as pg_check

        result = pg_check(config)
        return _transform_result(result)
    except ImportError:
        return {
            "ok": False,
            "error": "postgresql driver not installed",
            "driver": None,
            "db_version": None,
        }


def _transform_result(result: dict[str, Any]) -> dict[str, Any]:
    """Transform platform-specific result to unified format."""
    ok = result.get("ok", False)
    error = result.get("error")
    driver = result.get("driver")

    # Try to extract db_version from the result if available
    db_version = result.get("db_version") or result.get("version")

    return {
        "ok": ok,
        "error": error,
        "driver": driver,
        "db_version": db_version,
    }
