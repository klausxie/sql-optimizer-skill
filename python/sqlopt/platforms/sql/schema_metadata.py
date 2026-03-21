from __future__ import annotations

from typing import Any


def _get_platform_metadata_collector(config: dict[str, Any]):
    """Route to the correct platform-specific _collect_metadata implementation."""
    platform = str((config.get("db", {}) or {}).get("platform", "sql"))

    if platform == "mysql":
        from sqlopt.platforms.mysql.evidence import _collect_metadata

        return _collect_metadata
    elif platform == "postgresql":
        from sqlopt.platforms.postgresql.evidence import _collect_metadata

        return _collect_metadata
    else:
        from sqlopt.platforms.sql.metadata_evidence import _collect_metadata

        return _collect_metadata


def _extract_tables_from_sql_units(sql_units: list[dict[str, Any]]) -> list[str]:
    """Extract all unique table names from a list of sql_units.

    Only extracts from SQL text, NOT from resultMap or parameterMap.
    """
    from sqlopt.platforms.sql.metadata_evidence import _extract_tables

    all_tables: list[str] = []
    for unit in sql_units:
        sql = unit.get("sql", "")
        if sql:
            tables = _extract_tables(sql)
            for t in tables:
                if t not in all_tables:
                    all_tables.append(t)
    return all_tables


def collect_schema_metadata(
    config: dict[str, Any], sql_units: list[dict[str, Any]]
) -> dict[str, Any]:
    """Collect schema metadata for tables used in the provided SQL units.

    Args:
        config: Database configuration dict with db.platform and db.dsn
        sql_units: List of SQL unit dicts, each containing a "sql" key

    Returns:
        Dict with keys: tables, columns, indexes, tableStats
        - tables: list of table names used in the SQL
        - columns: list of {table, column, dataType, isNullable} dicts
        - indexes: list of {table, index, definition} dicts
        - tableStats: list of {table, estimatedRows} dicts
    """
    # Extract tables from SQL only (not resultMap/parameterMap)
    tables = _extract_tables_from_sql_units(sql_units)

    # Build a synthetic SQL with all tables for the metadata collector
    if not tables:
        return {"tables": [], "columns": [], "indexes": [], "tableStats": []}

    # Create a representative SQL to pass to the platform collector
    # The collector will extract tables again via its own _extract_tables
    # and use those for metadata queries
    sample_sql = "SELECT 1 FROM " + ",".join(tables)

    # Route to correct platform implementation
    collector = _get_platform_metadata_collector(config)
    result = collector(config, sample_sql)

    if not result.get("enabled", False):
        return {"tables": tables, "columns": [], "indexes": [], "tableStats": []}

    if not result.get("ok", False):
        # Return partial result with error info
        return {
            "tables": result.get("tables", tables),
            "columns": [],
            "indexes": [],
            "tableStats": [],
        }

    return {
        "tables": result.get("tables", tables),
        "columns": result.get("columns", []),
        "indexes": result.get("indexes", []),
        "tableStats": result.get("tableStats", []),
    }
