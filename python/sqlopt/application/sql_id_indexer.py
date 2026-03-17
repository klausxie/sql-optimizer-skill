"""SQL ID Indexer - Fast SQL ID lookup with prefix matching.

This module provides:
1. SQL ID alias generation (sqlKey, namespace.statementId, statementId, etc.)
2. Index building and persistence
3. Fast lookup with prefix matching
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils import statement_key


def _selection_aliases(unit: dict[str, Any]) -> set[str]:
    """Generate all possible aliases for a SQL unit."""
    sql_key = str(unit.get("sqlKey") or "").strip()
    statement_id = str(unit.get("statementId") or "").strip()
    variant_id = str(unit.get("variantId") or "").strip()
    namespace = str(unit.get("namespace") or "").strip()

    aliases: set[str] = set()

    if sql_key:
        aliases.add(sql_key)
        stmt_key = statement_key(sql_key)
        if stmt_key:
            aliases.add(stmt_key)

    if statement_id:
        aliases.add(statement_id)
        if namespace:
            aliases.add(f"{namespace}.{statement_id}")
        if variant_id:
            aliases.add(f"{statement_id}#{variant_id}")
            if namespace:
                aliases.add(f"{namespace}.{statement_id}#{variant_id}")

    return {alias for alias in aliases if alias}


def parse_path_sql_id(input_str: str) -> tuple[str | None, str | None]:
    """Parse absolute path + SQL ID format like '/path/mapper.xml:findUsers'.

    Args:
        input_str: Input string like '/path/to/User.xml:findUsers' or just 'findUsers'

    Returns:
        (file_path, sql_id) tuple. Either may be None if not in this format.
    """
    if not input_str:
        return None, None

    if ":" not in input_str:
        return None, input_str.strip()

    parts = input_str.rsplit(":", 1)
    if len(parts) != 2:
        return None, input_str.strip()

    file_path = parts[0].strip()
    sql_id = parts[1].strip()

    if not file_path or not sql_id:
        return None, sql_id or input_str.strip()

    return file_path, sql_id


def build_index(units: list[dict[str, Any]], project_root: Path) -> dict[str, Any]:
    """Build search index from SQL units.

    Args:
        units: List of SQL unit dictionaries
        project_root: Project root path

    Returns:
        Index dictionary ready for serialization
    """
    exact: dict[str, str] = {}
    statement_id_map: dict[str, list[str]] = {}
    prefix_3: dict[str, list[str]] = {}
    prefix_4: dict[str, list[str]] = {}
    files: dict[str, dict[str, Any]] = {}

    for unit in units:
        sql_key = str(unit.get("sqlKey") or "").strip()
        statement_id = str(unit.get("statementId") or "").strip()
        xml_path = str(unit.get("xmlPath") or "").strip()

        if not sql_key or not statement_id:
            continue

        file_key = xml_path
        if file_key:
            files[file_key] = {
                "mtime": int(datetime.now(timezone.utc).timestamp()),
                "sql_count": files.get(file_key, {}).get("sql_count", 0) + 1,
            }

        exact[sql_key] = file_key
        stmt_key = statement_key(sql_key)
        if stmt_key:
            exact[stmt_key] = file_key

        statement_id_map.setdefault(statement_id, []).append(file_key)
        if xml_path:
            statement_id_map[statement_id] = list(set(statement_id_map[statement_id]))

        if len(statement_id) >= 3:
            prefix_3_key = statement_id[:3].lower()
            prefix_3.setdefault(prefix_3_key, []).append(statement_id)

        if len(statement_id) >= 4:
            prefix_4_key = statement_id[:4].lower()
            prefix_4.setdefault(prefix_4_key, []).append(statement_id)

    for key in prefix_3:
        prefix_3[key] = list(set(prefix_3[key]))
    for key in prefix_4:
        prefix_4[key] = list(set(prefix_4[key]))

    return {
        "version": 1,
        "project_root": str(project_root.resolve()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "exact": exact,
        "statementId": statement_id_map,
        "prefix_3": prefix_3,
        "prefix_4": prefix_4,
        "files": files,
    }


def save_index(index: dict[str, Any], index_path: Path) -> None:
    """Save index to file."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def load_index(index_path: Path) -> dict[str, Any] | None:
    """Load index from file."""
    if not index_path.exists():
        return None
    try:
        with open(index_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def lookup_files(
    index: dict[str, Any], sql_ids: list[str]
) -> tuple[set[str], dict[str, list[str]]]:
    """Look up files for given SQL IDs.

    Args:
        index: Index dictionary
        sql_ids: List of SQL IDs to look up (can be sqlKey, statementId, or prefix)

    Returns:
        (found_files, missing_sql_ids)
    """
    exact = index.get("exact", {})
    statement_id_map = index.get("statementId", {})
    prefix_4 = index.get("prefix_4", {})
    prefix_3 = index.get("prefix_3", {})

    found_files: set[str] = set()
    missing: dict[str, list[str]] = {}

    for sql_id in sql_ids:
        if not sql_id:
            continue

        sql_id = sql_id.strip()
        files_for_id: list[str] = []

        if sql_id in exact:
            file_key = exact[sql_id]
            if file_key:
                files_for_id.append(file_key)

        if not files_for_id and sql_id in statement_id_map:
            files_for_id = statement_id_map[sql_id]

        if not files_for_id and len(sql_id) >= 4:
            prefix = sql_id[:4].lower()
            if prefix in prefix_4:
                for stmt_id in prefix_4[prefix]:
                    if stmt_id.startswith(sql_id):
                        if stmt_id in statement_id_map:
                            files_for_id.extend(statement_id_map[stmt_id])

        if not files_for_id and len(sql_id) >= 3:
            prefix = sql_id[:3].lower()
            if prefix in prefix_3:
                for stmt_id in prefix_3[prefix]:
                    if stmt_id.startswith(sql_id):
                        if stmt_id in statement_id_map:
                            files_for_id.extend(statement_id_map[stmt_id])

        files_for_id = list(set(files_for_id))

        if files_for_id:
            found_files.update(files_for_id)
        else:
            missing[sql_id] = []

    return found_files, missing


def is_index_valid(index: dict[str, Any], project_root: Path) -> bool:
    """Check if index is valid and up-to-date."""
    if index.get("version") != 1:
        return False

    stored_root = index.get("project_root", "")
    if Path(stored_root).resolve() != project_root.resolve():
        return False

    return True
