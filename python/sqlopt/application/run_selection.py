from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..utils import statement_key, statement_key_from_row


def _normalize_relative_project_path(project_root: Path, raw_path: str) -> str:
    text = str(raw_path or "").strip()
    if not text:
        raise ValueError("mapper path must not be empty")
    candidate = Path(text)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"mapper path must be inside project root: {text}") from exc
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"mapper path not found: {relative.as_posix()}")
    return relative.as_posix()


def normalize_run_selection(
    *,
    project_root: Path,
    mapper_paths: list[str] | None = None,
    sql_keys: list[str] | None = None,
) -> dict[str, Any] | None:
    normalized_mapper_paths: list[str] = []
    seen_mapper_paths: set[str] = set()
    for raw in mapper_paths or []:
        normalized = _normalize_relative_project_path(project_root, raw)
        if normalized not in seen_mapper_paths:
            normalized_mapper_paths.append(normalized)
            seen_mapper_paths.add(normalized)

    normalized_sql_keys: list[str] = []
    seen_sql_keys: set[str] = set()
    for raw in sql_keys or []:
        key = str(raw or "").strip()
        if not key or key in seen_sql_keys:
            continue
        normalized_sql_keys.append(key)
        seen_sql_keys.add(key)

    if not normalized_mapper_paths and not normalized_sql_keys:
        return None

    return {
        "present": True,
        "mapper_paths": normalized_mapper_paths,
        "sql_keys": normalized_sql_keys,
        "scanned_sql_keys": [],
        "selected_sql_keys": [],
        "scanned_count": 0,
        "selected_count": 0,
    }


def selection_matches(existing: dict[str, Any] | None, requested: dict[str, Any] | None) -> bool:
    if not existing and not requested:
        return True
    existing_payload = dict(existing or {})
    requested_payload = dict(requested or {})
    return (
        list(existing_payload.get("mapper_paths") or []) == list(requested_payload.get("mapper_paths") or [])
        and list(existing_payload.get("sql_keys") or []) == list(requested_payload.get("sql_keys") or [])
    )


def apply_selection_to_config(config: dict[str, Any], selection: dict[str, Any] | None) -> dict[str, Any]:
    if not selection:
        return config
    updated = deepcopy(config)
    updated["run_selection"] = {
        "present": True,
        "mapper_paths": list(selection.get("mapper_paths") or []),
        "sql_keys": list(selection.get("sql_keys") or []),
    }
    mapper_paths = list(selection.get("mapper_paths") or [])
    if mapper_paths:
        scan_cfg = dict(updated.get("scan") or {})
        scan_cfg["mapper_globs"] = mapper_paths
        updated["scan"] = scan_cfg
    return updated


def selection_scope(plan: dict[str, Any]) -> dict[str, Any] | None:
    selection = dict(plan.get("selection") or {})
    if not selection or not bool(selection.get("present")):
        return None
    return {
        "present": True,
        "mapper_paths": list(selection.get("mapper_paths") or []),
        "sql_keys": list(selection.get("sql_keys") or []),
        "scanned_count": int(selection.get("scanned_count") or 0),
        "selected_count": int(selection.get("selected_count") or 0),
    }


def filter_units_by_sql_keys(
    units: list[dict[str, Any]],
    sql_keys: list[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    requested = [str(row).strip() for row in (sql_keys or []) if str(row).strip()]
    if not requested:
        return list(units), []
    units_by_key = {str(row.get("sqlKey") or ""): row for row in units if str(row.get("sqlKey") or "").strip()}
    units_by_statement: dict[str, list[dict[str, Any]]] = {}
    for row in units:
        row_statement_key = statement_key_from_row(row)
        if row_statement_key:
            units_by_statement.setdefault(row_statement_key, []).append(row)

    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for key in requested:
        unit = units_by_key.get(key)
        if unit is None:
            statement_matches = units_by_statement.get(statement_key(key), [])
            if len(statement_matches) == 1:
                unit = statement_matches[0]
        if unit is None:
            missing.append(key)
            continue
        selected.append(unit)
    return selected, missing


def finalize_selection_summary(
    selection: dict[str, Any] | None,
    *,
    scanned_units: list[dict[str, Any]],
    selected_units: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not selection:
        return None
    payload = dict(selection)
    payload["present"] = True
    payload["scanned_sql_keys"] = [str(row.get("sqlKey") or "") for row in scanned_units if str(row.get("sqlKey") or "").strip()]
    payload["selected_sql_keys"] = [str(row.get("sqlKey") or "") for row in selected_units if str(row.get("sqlKey") or "").strip()]
    payload["scanned_count"] = len(payload["scanned_sql_keys"])
    payload["selected_count"] = len(payload["selected_sql_keys"])
    return payload
