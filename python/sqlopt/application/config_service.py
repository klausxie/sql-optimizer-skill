from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import StageError
from ..platforms.dispatch import check_db_connectivity
from ..config import load_config


_DSN_PLACEHOLDERS = (
    "<user>",
    "<password>",
    "<database>",
    "<dbname>",
    "<host>",
    "<port>",
)


def _mask_dsn(dsn: str) -> str:
    text = str(dsn or "").strip()
    if "://" not in text or "@" not in text:
        return text
    scheme, rest = text.split("://", 1)
    creds, tail = rest.split("@", 1)
    if ":" not in creds:
        return f"{scheme}://{creds}@{tail}"
    user, _password = creds.split(":", 1)
    return f"{scheme}://{user}:***@{tail}"


def dsn_contains_placeholders(dsn: str) -> bool:
    lowered = str(dsn or "").strip().lower()
    if not lowered:
        return False
    if any(marker in lowered for marker in _DSN_PLACEHOLDERS):
        return True
    return "<" in lowered and ">" in lowered


def prepare_runtime_prerequisites(
    config: dict[str, Any],
    *,
    to_stage: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    target_stage = str(to_stage or "").strip().lower()
    requires_db = target_stage in {"validate", "patch_generate", "report"}
    result = {
        "requires_db": requires_db,
        "db_reachable": None,
        "warning": None,
    }
    if not requires_db:
        return result

    db_cfg = dict(config.get("db") or {})
    dsn = str(db_cfg.get("dsn") or "").strip()
    if dsn_contains_placeholders(dsn):
        config_hint = f" in {config_path}" if config_path is not None else ""
        raise StageError(
            f"database dsn still contains placeholders{config_hint}: {_mask_dsn(dsn)}. "
            "Replace db.dsn with a real connection string or run sqlopt-cli validate-config first.",
            reason_code="DB_CONNECTION_FAILED",
        )

    connectivity = check_db_connectivity(config)
    db_reachable = bool(connectivity.get("ok", False))
    validate_cfg = dict(config.get("validate") or {})
    validate_cfg["db_reachable"] = db_reachable
    config["validate"] = validate_cfg
    result["db_reachable"] = db_reachable

    if db_reachable:
        return result

    error_text = str(connectivity.get("error") or "unknown connection error").strip()
    warning = f"database connectivity check failed for {_mask_dsn(dsn)}: {error_text}"
    result["warning"] = warning
    if not bool(validate_cfg.get("allow_db_unreachable_fallback", True)):
        config_hint = f" in {config_path}" if config_path is not None else ""
        raise StageError(
            f"{warning}. Fix db.dsn{config_hint} or re-run sqlopt-cli validate-config.",
            reason_code="DB_CONNECTION_FAILED",
        )
    return result


def validate_config(config_path: Path, *, check_connectivity: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    results: dict[str, Any] = {
        "valid": True,
        "config_path": str(config_path),
        "checks": [],
    }

    required_fields = [
        ("project", "root_path"),
        ("scan", "mapper_globs"),
        ("db", "platform"),
        ("db", "dsn"),
        ("llm", "provider"),
    ]

    for *path, field in required_fields:
        current: Any = config
        field_path = ".".join(path + [field])
        try:
            for key in path:
                current = current[key]
            if field in current:
                results["checks"].append(
                    {
                        "field": field_path,
                        "status": "ok",
                        "value": str(current[field])[:50],
                    }
                )
            else:
                results["checks"].append(
                    {
                        "field": field_path,
                        "status": "missing",
                        "message": "Required field is missing",
                    }
                )
                results["valid"] = False
        except (KeyError, TypeError):
            results["checks"].append(
                {
                    "field": field_path,
                    "status": "missing",
                    "message": "Parent section is missing",
                }
            )
            results["valid"] = False

    dsn = config.get("db", {}).get("dsn", "")
    if dsn_contains_placeholders(str(dsn)):
        results["checks"].append(
            {
                "field": "db.dsn",
                "status": "invalid",
                "message": "DSN contains placeholders; replace db.dsn with real connection values before running DB-backed stages",
                "value": _mask_dsn(str(dsn)),
            }
        )
        results["valid"] = False
    elif check_connectivity:
        connectivity = check_db_connectivity(config)
        ok = bool(connectivity.get("ok", False))
        message = "database connection verified" if ok else str(connectivity.get("error") or "database connection failed").strip()
        results["checks"].append(
            {
                "field": "db.connection",
                "status": "ok" if ok else "error",
                "message": message,
                "value": _mask_dsn(str(dsn)),
                "reason_code": connectivity.get("reason_code"),
            }
        )
        if not ok:
            results["valid"] = False

    mapper_globs = config.get("scan", {}).get("mapper_globs", [])
    if mapper_globs:
        project_root = Path(config.get("project", {}).get("root_path", ".")).resolve()
        import glob as glob_module

        found_files: list[str] = []
        for pattern in mapper_globs:
            full_pattern = str(project_root / pattern)
            matches = glob_module.glob(full_pattern, recursive=True)
            found_files.extend(matches)

        results["checks"].append(
            {
                "field": "scan.mapper_globs",
                "status": "ok" if found_files else "warning",
                "message": f"Found {len(found_files)} mapper file(s)" if found_files else "No mapper files found",
            }
        )

    return results
