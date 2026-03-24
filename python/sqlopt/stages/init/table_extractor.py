"""Table schema extractor for Init stage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from sqlopt.contracts.init import TableSchema

if TYPE_CHECKING:
    from sqlopt.common.db_connector import DBConnector

logger = logging.getLogger(__name__)


def extract_table_schemas(
    table_names: List[str],
    db_connector: "DBConnector",
    platform: str,
) -> Dict[str, TableSchema]:
    """Extract table schemas from database.

    Args:
        table_names: List of table names to extract schemas for.
        db_connector: Database connector instance.
        platform: Database platform ('postgresql' or 'mysql').

    Returns:
        Dict mapping table name to TableSchema.
    """
    if not table_names:
        return {}

    schemas: Dict[str, TableSchema] = {}

    for table_name in table_names:
        try:
            schema = _extract_single_table(table_name, db_connector, platform)
            if schema:
                schemas[table_name] = schema
        except (ConnectionError, RuntimeError) as e:  # noqa: PERF203
            logger.warning("Failed to extract schema for table %s: %s", table_name, e)

    return schemas


def _extract_single_table(
    table_name: str,
    db_connector: "DBConnector",
    platform: str,
) -> TableSchema | None:
    """Extract schema for a single table."""
    if platform == "postgresql":
        return _extract_postgresql_table(table_name, db_connector)
    if platform == "mysql":
        return _extract_mysql_table(table_name, db_connector)
    logger.warning("Unsupported platform: %s", platform)
    return None


def _extract_postgresql_table(table_name: str, db_connector: "DBConnector") -> TableSchema | None:
    """Extract PostgreSQL table schema."""
    columns_query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
    """
    columns = _execute_safe(db_connector, columns_query, (table_name,))

    if not columns:
        logger.warning("No columns found for table: %s", table_name)
        return None

    pk_query = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_name = %s
    """
    pk_result = _execute_safe(db_connector, pk_query, (table_name,))
    primary_keys = {row["column_name"] for row in pk_result} if pk_result else set()

    column_list = [
        {
            "name": col["column_name"],
            "type": col["data_type"],
            "nullable": col["is_nullable"] == "YES",
            "primaryKey": col["column_name"] in primary_keys,
        }
        for col in columns
    ]

    indexes_query = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = %s
    """
    indexes = _execute_safe(db_connector, indexes_query, (table_name,))

    index_list = []
    for idx in indexes:
        indexdef = idx["indexdef"]
        index_name = idx["indexname"]
        is_unique = "UNIQUE" in indexdef.upper()

        col_start = indexdef.find("(")
        col_end = indexdef.find(")")
        if col_start != -1 and col_end != -1:
            cols_str = indexdef[col_start + 1 : col_end]
            idx_columns = [c.strip() for c in cols_str.split(",")]
        else:
            idx_columns = []

        if is_unique:
            idx_type = "UNIQUE"
        elif "btree" in indexdef.lower():
            idx_type = "BTREE"
        elif "hash" in indexdef.lower():
            idx_type = "HASH"
        else:
            idx_type = "INDEX"

        index_list.append(
            {
                "name": index_name,
                "columns": idx_columns,
                "unique": is_unique,
                "type": idx_type,
            }
        )

    stats_query = """
        SELECT reltuples, relpages
        FROM pg_class
        WHERE relname = %s
    """
    stats_result = _execute_safe(db_connector, stats_query, (table_name,))

    statistics: Dict[str, Any] = {}
    if stats_result and len(stats_result) > 0:
        row = stats_result[0]
        reltuples = row.get("reltuples", 0)
        row_count = int(reltuples) if reltuples and reltuples >= 0 else None
        relpages = row.get("relpages", 0)
        total_size_bytes = int(relpages * 8192) if relpages else None

        statistics = {
            "rowCount": row_count,
            "totalSizeBytes": total_size_bytes,
        }
    else:
        statistics = {"rowCount": None}

    return TableSchema(
        columns=column_list,
        indexes=index_list,
        statistics=statistics,
    )


def _extract_mysql_table(table_name: str, db_connector: "DBConnector") -> TableSchema | None:
    """Extract MySQL table schema."""
    columns_query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = %s
    """
    columns = _execute_safe(db_connector, columns_query, (table_name,))

    if not columns:
        logger.warning("No columns found for table: %s", table_name)
        return None

    pk_query = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_NAME = %s
            AND CONSTRAINT_NAME = 'PRIMARY'
    """
    pk_result = _execute_safe(db_connector, pk_query, (table_name,))
    primary_keys = {row["COLUMN_NAME"] for row in pk_result} if pk_result else set()

    column_list = [
        {
            "name": col["COLUMN_NAME"],
            "type": col["DATA_TYPE"],
            "nullable": col["IS_NULLABLE"] == "YES",
            "primaryKey": col["COLUMN_NAME"] in primary_keys,
        }
        for col in columns
    ]

    indexes_query = f"SHOW INDEX FROM {table_name}"
    indexes = _execute_safe(db_connector, indexes_query, None)

    index_map: Dict[str, Dict[str, Any]] = {}
    for idx in indexes:
        index_name = idx.get("Key_name", "")
        if index_name == "PRIMARY":
            is_unique = True
            idx_type = "PRIMARY"
        else:
            is_unique = idx.get("Non_unique", 1) == 0
            idx_type = "UNIQUE" if is_unique else "INDEX"

        if index_name not in index_map:
            index_map[index_name] = {
                "name": index_name,
                "columns": [],
                "unique": is_unique,
                "type": idx_type,
            }

        index_map[index_name]["columns"].append(idx.get("Column_name", ""))

    index_list = list(index_map.values())

    stats_query = f"SHOW TABLE STATUS WHERE Name = '{table_name}'"
    stats_result = _execute_safe(db_connector, stats_query, None)

    statistics: Dict[str, Any] = {}
    if stats_result and len(stats_result) > 0:
        row = stats_result[0]
        row_count = row.get("Rows")
        if row_count is not None:
            row_count = int(row_count) if row_count else None

        data_length = row.get("Data_length", 0) or 0
        index_length = row.get("Index_length", 0) or 0
        total_size_bytes = int(data_length + index_length) if (data_length or index_length) else None

        statistics = {
            "rowCount": row_count,
            "totalSizeBytes": total_size_bytes,
        }
    else:
        statistics = {"rowCount": None}

    return TableSchema(
        columns=column_list,
        indexes=index_list,
        statistics=statistics,
    )


def _execute_safe(
    db_connector: "DBConnector",
    sql: str,
    params: tuple | None,
) -> List[Dict[str, Any]]:
    """Execute query safely, handling connection errors."""
    try:
        if params:
            formatted_sql = sql % tuple(f"'{p}'" for p in params) if "%s" in sql else sql
            return db_connector.execute_query(formatted_sql)
        return db_connector.execute_query(sql)
    except (ConnectionError, RuntimeError) as e:
        logger.warning("Query failed: %s - Error: %s", sql, e)
        return []
