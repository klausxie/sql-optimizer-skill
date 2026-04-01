"""Table schema extractor for Init stage."""

from __future__ import annotations

import html
import logging
import re
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from sqlopt.contracts.init import FieldDistribution, TableSchema

if TYPE_CHECKING:
    from sqlopt.common.config import FieldDistributionConcurrencyConfig
    from sqlopt.common.db_connector import DBConnector

logger = logging.getLogger(__name__)

TABLE_REFERENCE_FUNCTIONS = {
    "extract",
    "overlay",
    "substring",
    "trim",
}

CLAUSE_BOUNDARY_PATTERN = (
    r"(?=\b(?:INNER|LEFT|RIGHT|FULL|OUTER|CROSS)\s+JOIN\b|\bJOIN\b|\bWHERE\b|"
    r"\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bEXCEPT\b|\bINTERSECT\b|$)"
)
CONDITION_OPERATOR_PATTERN = r"(?:=|<>|!=|<=|>=|<|>|LIKE\b|ILIKE\b|IN\b|BETWEEN\b|IS\b)"
SQL_FIELD_KEYWORDS = {
    "and",
    "or",
    "not",
    "in",
    "is",
    "null",
    "true",
    "false",
    "like",
    "ilike",
    "between",
    "exists",
    "select",
    "from",
    "where",
    "join",
    "inner",
    "left",
    "right",
    "outer",
    "cross",
    "group",
    "order",
    "having",
    "limit",
    "offset",
    "on",
    "as",
}


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
    except Exception as e:  # noqa: BLE001
        logger.warning("Query failed: %s - Error: %s", sql, e)
        return []


def extract_table_references_from_sql(sql_text: str) -> List[tuple[str, str | None]]:
    """Extract table references and aliases from SQL text."""
    normalized_sql = _normalize_sql_for_analysis(sql_text)
    if not normalized_sql:
        return []
    normalized_sql = _strip_function_calls_for_table_scan(normalized_sql)

    pattern = re.compile(
        r"\b(?:FROM|JOIN|UPDATE|INTO|DELETE\s+FROM)\s+"
        r"(?P<table>[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)"
        r"(?:\s+(?:AS\s+)?(?P<alias>(?!(?:where|join|inner|left|right|full|outer|cross|on|group|order|having|limit|union|except|intersect|set|values)\b)[a-zA-Z_][a-zA-Z0-9_]*))?",
        re.IGNORECASE,
    )

    references: List[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for match in pattern.finditer(normalized_sql):
        table_name = _normalize_identifier(match.group("table"))
        alias = match.group("alias")
        if alias and alias.lower() in SQL_FIELD_KEYWORDS:
            alias = None
        normalized_ref = (table_name, alias.lower() if alias else None)
        if normalized_ref not in seen:
            seen.add(normalized_ref)
            references.append(normalized_ref)
    return references


def _strip_function_calls_for_table_scan(sql_text: str) -> str:
    """Strip function bodies that may legally contain FROM as an argument separator.

    Standard SQL functions like EXTRACT and SUBSTRING use FROM inside their
    argument list, which would otherwise be mistaken for a table clause by the
    lightweight table-reference regex below.
    """
    if not sql_text:
        return sql_text

    result: list[str] = []
    idx = 0
    length = len(sql_text)

    while idx < length:
        char = sql_text[idx]
        if char.isalpha() or char == "_":
            start = idx
            idx += 1
            while idx < length and (sql_text[idx].isalnum() or sql_text[idx] == "_"):
                idx += 1
            identifier = sql_text[start:idx]
            lookahead = idx
            while lookahead < length and sql_text[lookahead].isspace():
                lookahead += 1

            if identifier.lower() in TABLE_REFERENCE_FUNCTIONS and lookahead < length and sql_text[lookahead] == "(":
                end_idx = _find_matching_parenthesis(sql_text, lookahead)
                if end_idx == -1:
                    result.append(identifier)
                    continue
                result.append(identifier.upper())
                idx = end_idx + 1
                continue

            result.append(identifier)
            continue

        result.append(char)
        idx += 1

    return "".join(result)


def _find_matching_parenthesis(sql_text: str, open_idx: int) -> int:
    depth = 0
    for idx in range(open_idx, len(sql_text)):
        if sql_text[idx] == "(":
            depth += 1
        elif sql_text[idx] == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def extract_condition_fields_by_table(sql_text: str) -> Dict[str, set[str]]:
    """Extract condition fields grouped by table name."""
    normalized_sql = _normalize_sql_for_analysis(sql_text)
    table_refs = extract_table_references_from_sql(sql_text)
    if not normalized_sql or not table_refs:
        return {}

    alias_map: Dict[str, str] = {}
    ordered_tables: List[str] = []
    for table_name, alias in table_refs:
        if table_name not in ordered_tables:
            ordered_tables.append(table_name)
        alias_map[table_name] = table_name
        if alias:
            alias_map[alias] = table_name

    fields_by_table: Dict[str, set[str]] = {table_name: set() for table_name in ordered_tables}
    clauses = _extract_condition_clauses(normalized_sql)
    if not clauses:
        return fields_by_table

    qualified_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b")
    for clause in clauses:
        for qualifier, column_name in qualified_pattern.findall(clause):
            table_name = alias_map.get(qualifier.lower())
            if table_name:
                fields_by_table.setdefault(table_name, set()).add(column_name.lower())

        clause_without_qualified = qualified_pattern.sub(" ", clause)
        unqualified_fields = _extract_unqualified_condition_fields(clause_without_qualified)
        if not unqualified_fields:
            continue
        if len(ordered_tables) == 1:
            fields_by_table[ordered_tables[0]].update(unqualified_fields)
            continue
        for table_name in ordered_tables:
            fields_by_table[table_name].update(unqualified_fields)

    return {table_name: fields for table_name, fields in fields_by_table.items() if fields}


def extract_where_fields_from_sql(sql_text: str) -> List[str]:
    """Extract field names from WHERE clause in SQL text.

    Handles MyBatis dynamic SQL tags by filtering them out before parsing.

    Args:
        sql_text: SQL text to parse (may contain MyBatis tags).

    Returns:
        List of field/column names found in WHERE conditions.
    """
    fields_by_table = extract_condition_fields_by_table(sql_text)
    field_names = {field for fields in fields_by_table.values() for field in fields}
    return sorted(field_names)


def extract_field_distributions(
    table_name: str,
    column_names: List[str],
    db_connector: "DBConnector",
    platform: str,
    top_n: int = 10,
    progress_callback: Callable[[str, tuple[int, int] | None], None] | None = None,
) -> List[FieldDistribution]:
    distributions: List[FieldDistribution] = []
    unique_columns = sorted(set(column_names))

    for idx, col in enumerate(unique_columns):
        if progress_callback:
            progress_callback(f"Extracting distribution: {table_name}.{col}", (idx + 1, len(unique_columns)))
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

    total_query = f"SELECT COUNT(*) AS count FROM {safe_table}"
    total_result = _execute_safe(db_connector, total_query, None)
    total_count = _extract_count_value(total_result)

    distinct_query = f"SELECT COUNT(DISTINCT {safe_column}) AS count FROM {safe_table}"
    distinct_result = _execute_safe(db_connector, distinct_query, None)
    distinct_count = _extract_count_value(distinct_result)

    null_query = f"SELECT COUNT(*) AS count FROM {safe_table} WHERE {safe_column} IS NULL"
    null_result = _execute_safe(db_connector, null_query, None)
    null_count = _extract_count_value(null_result)

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
        top_values.extend({"value": str(row.get("value", "")), "count": row.get("count", 0)} for row in top_result)

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
        total_count=int(total_count) if total_count else 0,
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


def _normalize_sql_for_analysis(sql_text: str) -> str:
    if not sql_text:
        return ""

    normalized = html.unescape(sql_text)
    normalized = re.sub(r"<!--.*?-->", " ", normalized, flags=re.DOTALL)
    normalized = re.sub(r"#\{[^}]*\}", " ? ", normalized)
    normalized = re.sub(r"\$\{[^}]*\}", " ? ", normalized)
    normalized = re.sub(r"<where\b[^>]*>", " WHERE ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</where>", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<trim\b[^>]*prefix\s*=\s*['\"]WHERE['\"][^>]*>", " WHERE ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</trim>", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</?(?:if|choose|when|otherwise|foreach|set)\b[^>]*>", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<bind\b[^>]*/?>", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<include\b[^>]*/?>", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"'(?:''|[^'])*'", " ", normalized)
    normalized = normalized.replace("`", "").replace('"', "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_identifier(identifier: str) -> str:
    cleaned = identifier.strip().strip("`").strip('"')
    return cleaned.split(".")[-1].lower()


def _extract_condition_clauses(sql_text: str) -> List[str]:
    patterns = [
        re.compile(
            r"\bWHERE\b\s+(?P<clause>.+?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bEXCEPT\b|\bINTERSECT\b|$)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\bHAVING\b\s+(?P<clause>.+?)(?=\bORDER\s+BY\b|\bLIMIT\b|\bUNION\b|\bEXCEPT\b|\bINTERSECT\b|$)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(rf"\bON\b\s+(?P<clause>.+?){CLAUSE_BOUNDARY_PATTERN}", re.IGNORECASE | re.DOTALL),
    ]

    clauses: List[str] = []
    for pattern in patterns:
        clauses.extend(match.group("clause") for match in pattern.finditer(sql_text))
    return clauses


def _extract_unqualified_condition_fields(clause: str) -> set[str]:
    comparison_pattern = re.compile(
        rf"(?:\b[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*)?"
        rf"([a-zA-Z_][a-zA-Z0-9_]*)"
        rf"(?:\s*\))?\s*{CONDITION_OPERATOR_PATTERN}",
        re.IGNORECASE,
    )

    fields: set[str] = set()
    for match in comparison_pattern.finditer(clause):
        column_name = match.group(1).lower()
        if column_name not in SQL_FIELD_KEYWORDS:
            fields.add(column_name)
    return fields


def _extract_count_value(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    row = rows[0]
    for key, value in row.items():
        if key.lower() == "count":
            return int(value) if value is not None else 0
    first_value = next(iter(row.values()), 0)
    return int(first_value) if first_value is not None else 0


@dataclass
class _ColumnTaskResult:
    table_name: str
    column_name: str
    success: bool
    distribution: FieldDistribution | None
    error: str | None


def _column_task(
    pair: tuple[str, str],
    connector_factory: Callable[[], "DBConnector"],
    platform: str,
    top_n: int,
    timeout_per_field: int,
    retry_count: int,
) -> _ColumnTaskResult:
    table_name, column_name = pair
    last_error: str | None = None

    for attempt in range(1, retry_count + 2):
        connector: "DBConnector" | None = None
        started_at = time.perf_counter()
        try:
            connector = connector_factory()
            timeout_seconds = max(float(timeout_per_field), 0.0)
            dist = _extract_single_column_distribution(table_name, column_name, connector, platform, top_n)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            if timeout_seconds > 0 and elapsed_ms > timeout_seconds * 1000:
                raise TimeoutError(f"field extraction exceeded timeout {timeout_seconds}s (elapsed={elapsed_ms:.1f}ms)")
            return _ColumnTaskResult(
                table_name=table_name,
                column_name=column_name,
                success=True,
                distribution=dist,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        finally:
            if connector is not None:
                with suppress(Exception):
                    connector.disconnect()

        if attempt < retry_count + 1:
            delay = 1.0 * (2 ** (attempt - 1))
            time.sleep(delay)

    return _ColumnTaskResult(
        table_name=table_name,
        column_name=column_name,
        success=False,
        distribution=None,
        error=last_error,
    )


def extract_field_distributions_parallel(
    field_by_table: dict[str, set[str]],
    connector_factory: Callable[[], "DBConnector"],
    platform: str,
    config: "FieldDistributionConcurrencyConfig",
    top_n: int = 10,
    progress_callback: Callable[[str, tuple[int, int] | None], None] | None = None,
) -> list[FieldDistribution]:
    pairs: list[tuple[str, str]] = [
        (tbl, col) for tbl in sorted(field_by_table.keys()) for col in sorted(field_by_table[tbl])
    ]

    if not pairs:
        return []

    total = len(pairs)

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures: dict[Future, int] = {}
        for idx, pair in enumerate(pairs):
            future = executor.submit(
                _column_task,
                pair,
                connector_factory,
                platform,
                top_n,
                config.timeout_per_field,
                config.retry_count,
            )
            futures[future] = idx

        completed = 0
        distributions: list[FieldDistribution] = []

        while futures:
            done, _ = wait(tuple(futures.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                idx = futures.pop(future)
                pair = pairs[idx]
                result = future.result()

                if result.success and result.distribution is not None:
                    distributions.append(result.distribution)
                else:
                    tbl, col = pair
                    logger.warning("Failed to extract distribution for %s.%s: %s", tbl, col, result.error)

                completed += 1
                if progress_callback:
                    progress_callback(
                        f"Extracting distribution: {pair[0]}.{pair[1]}",
                        (completed, total),
                    )

    return distributions
