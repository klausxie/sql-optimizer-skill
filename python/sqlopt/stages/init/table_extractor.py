"""Table schema extractor for Init stage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from sqlopt.contracts.init import FieldDistribution, TableSchema

if TYPE_CHECKING:
    from sqlopt.common.db_connector import DBConnector

logger = logging.getLogger(__name__)


def extract_table_schemas(
    table_names: List[str],
    db_connector: "DBConnector",
    platform: str,
    progress_callback: Callable[[str, tuple[int, int] | None], None] | None = None,
) -> Dict[str, TableSchema]:
    if not table_names:
        return {}

    schemas: Dict[str, TableSchema] = {}

    for idx, table_name in enumerate(table_names):
        if progress_callback:
            progress_callback(f"Extracting schema: {table_name}", (idx + 1, len(table_names)))
        try:
            schema = _extract_single_table(table_name, db_connector, platform)
            if schema:
                schemas[table_name] = schema
        except (ConnectionError, RuntimeError) as e:
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
    """Execute query safely, handling connection and operational errors."""
    try:
        return db_connector.execute_query(sql, params)
    except (ConnectionError, RuntimeError, Exception) as e:
        logger.warning("Query failed: %s - Error: %s", sql, e)
        return []


def extract_where_fields_from_sql(sql_text: str) -> List[str]:
    """Extract field names from WHERE clause in SQL text.

    Handles MyBatis dynamic SQL tags by filtering them out before parsing.

    Args:
        sql_text: SQL text to parse (may contain MyBatis tags).

    Returns:
        List of field/column names found in WHERE conditions.
    """
    import re

    if not sql_text:
        return []

    mybatis_patterns = [
        r"#{[^}]*}",  # #{field_name}
        r"\${[^}]*}",  # ${field_name}
        r"<if[^>]*>.*?</if>",  # <if test="...">...</if>
        r"<where[^>]*>",  # <where> tags
        r"<set[^>]*>",  # <set> tags
        r"<trim[^>]*>.*?</trim>",  # <trim>...</trim>
        r"<choose[^>]*>.*?</choose>",  # <choose>...</choose>
        r"<when[^>]*>.*?</when>",  # <when>...</when>
        r"<otherwise[^>]*>.*?</otherwise>",  # <otherwise>...</otherwise>
        r"<foreach[^>]*>.*?</foreach>",  # <foreach>...</foreach>
        r"<bind[^>]*>.*?</bind>",  # <bind>...</bind>
        r"<include[^>]*>.*?</include>",  # <include...>...</include>
        r"&lt;if.*?&gt;",  # escaped <if>
        r"&gt;",  # escaped >
        r"&lt;",  # escaped <
    ]

    cleaned_sql = sql_text
    for pattern in mybatis_patterns:
        cleaned_sql = re.sub(pattern, " ", cleaned_sql, flags=re.IGNORECASE | re.DOTALL)

    sql_keywords = {
        "select",
        "from",
        "where",
        "and",
        "or",
        "not",
        "in",
        "is",
        "null",
        "true",
        "false",
        "like",
        "between",
        "exists",
        "any",
        "all",
        "some",
        "case",
        "when",
        "then",
        "else",
        "end",
        "as",
        "on",
        "join",
        "inner",
        "left",
        "right",
        "outer",
        "cross",
        "group",
        "by",
        "order",
        "having",
        "limit",
        "offset",
        "union",
        "intersect",
        "except",
        "insert",
        "update",
        "delete",
        "values",
        "set",
        "into",
        "create",
        "drop",
        "alter",
        "table",
        "index",
        "view",
        "procedure",
        "function",
        "trigger",
        "grant",
        "revoke",
        "commit",
        "rollback",
        "savepoint",
        "lock",
        "unlock",
        "call",
        "explain",
        "describe",
        "show",
        "use",
        "database",
        "schema",
    }

    field_names: set[str] = set()

    where_pattern = r"\bWHERE\s+(.+?)(?:\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|$)"
    match = re.search(where_pattern, cleaned_sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []

    where_clause = match.group(1)

    condition_pattern = r"(?:AND|OR)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|<|>|<=|>=|<>|!=|LIKE|IN|BETWEEN|IS)"
    for m in re.finditer(condition_pattern, where_clause, re.IGNORECASE):
        field = m.group(1).lower()
        if field not in sql_keywords:
            field_names.add(field)

    comparison_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|<|>|<=|>=|<>|!=|LIKE|IN|BETWEEN|IS)\s+"
    for m in re.finditer(comparison_pattern, where_clause, re.IGNORECASE):
        field = m.group(1).lower()
        if field not in sql_keywords:
            field_names.add(field)

    return list(field_names)


def extract_field_distributions(
    table_name: str,
    column_names: List[str],
    db_connector: "DBConnector",
    platform: str,
    top_n: int = 10,
    progress_callback: Callable[[str, tuple[int, int] | None], None] | None = None,
) -> List[FieldDistribution]:
    distributions: List[FieldDistribution] = []

    for idx, col in enumerate(column_names):
        if progress_callback:
            progress_callback(f"Extracting distribution: {table_name}.{col}", (idx + 1, len(column_names)))
        try:
            dist = _extract_single_column_distribution(table_name, col, db_connector, platform, top_n)
            if dist:
                distributions.append(dist)
        except (ConnectionError, RuntimeError) as e:
            logger.warning("Failed to extract distribution for %s.%s: %s", table_name, col, e)

    return distributions


def _extract_single_column_distribution(
    table_name: str,
    column_name: str,
    db_connector: "DBConnector",
    platform: str,
    top_n: int,
) -> FieldDistribution | None:
    """Extract distribution for a single column."""
    safe_table = _safe_identifier(table_name, platform)
    safe_column = _safe_identifier(column_name, platform)

    distinct_query = f"SELECT COUNT(DISTINCT {safe_column}) FROM {safe_table}"
    distinct_result = _execute_safe(db_connector, distinct_query, None)
    distinct_count = distinct_result[0].get("count", 0) if distinct_result else 0

    null_query = f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_column} IS NULL"
    null_result = _execute_safe(db_connector, null_query, None)
    null_count = null_result[0].get("count", 0) if null_result else 0

    top_values: List[Dict[str, Any]] = []
    if platform == "postgresql":
        top_query = f"""
            SELECT {safe_column} as value, COUNT(*) as count
            FROM {safe_table}
            WHERE {safe_column} IS NOT NULL
            GROUP BY {safe_column}
            ORDER BY COUNT(*) DESC
            LIMIT %s
        """
        top_result = _execute_safe(db_connector, top_query, (top_n,))
    else:
        top_query = f"""
            SELECT {safe_column} as value, COUNT(*) as count
            FROM {safe_table}
            WHERE {safe_column} IS NOT NULL
            GROUP BY {safe_column}
            ORDER BY COUNT(*) DESC
            LIMIT %s
        """
        top_result = _execute_safe(db_connector, top_query, (top_n,))

    if top_result:
        for row in top_result:
            top_values.append({"value": str(row.get("value", "")), "count": row.get("count", 0)})

    min_max_query = f"SELECT MIN({safe_column}) as min_val, MAX({safe_column}) as max_val FROM {safe_table}"
    min_max_result = _execute_safe(db_connector, min_max_query, None)
    min_value = None
    max_value = None
    if min_max_result and len(min_max_result) > 0:
        min_value = str(min_max_result[0].get("min_val", "")) if min_max_result[0].get("min_val") is not None else None
        max_value = str(min_max_result[0].get("max_val", "")) if min_max_result[0].get("max_val") is not None else None

    return FieldDistribution(
        table_name=table_name,
        column_name=column_name,
        distinct_count=int(distinct_count) if distinct_count else 0,
        null_count=int(null_count) if null_count else 0,
        top_values=top_values,
        min_value=min_value,
        max_value=max_value,
    )


def _safe_identifier(name: str, platform: str) -> str:
    """Safely quote an identifier based on platform."""
    if platform == "postgresql":
        return f'"{name}"'
    return f"`{name}`"
