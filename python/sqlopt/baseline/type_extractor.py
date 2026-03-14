"""Type extractor for PostgreSQL tables."""

from typing import Any


# In-memory cache for column types: {(schema, table): {column: type}}
_column_type_cache: dict[tuple[str, str], dict[str, str]] = {}


def _get_sql_connect() -> tuple[Any | None, str | None]:
    """Get SQL connection function and driver name."""
    try:
        import psycopg  # type: ignore

        return psycopg.connect, "psycopg"
    except Exception:
        pass

    try:
        import psycopg2  # type: ignore

        return psycopg2.connect, "psycopg2"
    except Exception:
        return None, None


def extract_column_types(config: dict[str, Any], table_name: str) -> dict[str, str]:
    """
    Extract column types from a PostgreSQL table.

    Args:
        config: Configuration dict with db.dsn for database connection
        table_name: Table name, optionally schema-qualified (e.g., 'public.users')

    Returns:
        Dict mapping column_name -> data_type
    """
    db_cfg = config.get("db", {})
    dsn = db_cfg.get("dsn")
    if not dsn:
        return {}

    # Parse schema and table name
    if "." in table_name:
        schema, table = table_name.split(".", 1)
    else:
        schema = "public"
        table = table_name

    # Check cache first
    cache_key = (schema, table)
    if cache_key in _column_type_cache:
        return _column_type_cache[cache_key]

    connect, driver = _get_sql_connect()
    if connect is None:
        return {}

    try:
        conn = connect(dsn)
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table),
                )
                results = cur.fetchall()
                column_types = {row[0]: row[1] for row in results}

                # Cache the result
                _column_type_cache[cache_key] = column_types

                return column_types
            finally:
                cur.close()
        finally:
            conn.close()
    except Exception:
        # Return empty dict on any error
        return {}
