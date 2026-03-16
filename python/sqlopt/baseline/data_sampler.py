"""Data sampler for PostgreSQL tables."""

from __future__ import annotations

from typing import Any


def _get_sql_connect():
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


def sample_table_data(
    config: dict[str, Any], table_name: str, limit: int = 100
) -> list[dict]:
    """Sample rows from a PostgreSQL table using random sampling.

    Args:
        config: Configuration dict with db.dsn for database connection
        table_name: Name of the table to sample from (can include schema like 'public.table')
        limit: Maximum number of rows to sample (default: 100)

    Returns:
        List of dicts, each dict representing one row

    Raises:
        Exception: If DSN is not set or connection fails
    """
    dsn = (config.get("db", {}) or {}).get("dsn")
    if not dsn:
        raise ValueError("db.dsn not set in config")

    connect, driver = _get_sql_connect()
    if connect is None:
        raise RuntimeError("No PostgreSQL driver available (psycopg or psycopg2)")

    # Handle schema-qualified table names
    table_identifier = table_name
    if "." in table_name:
        schema, tbl = table_name.split(".", 1)
        # Quote identifiers to handle special characters
        table_identifier = f'"{schema}"."{tbl}"'
    else:
        table_identifier = f'"{table_name}"'

    query = f"SELECT * FROM {table_identifier} ORDER BY RANDOM() LIMIT %s"

    try:
        with connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                columns = (
                    [desc[0] for desc in cur.description] if cur.description else []
                )
                rows = cur.fetchall()

                # Convert to list of dicts
                result = []
                for row in rows:
                    result.append(dict(zip(columns, row)))

                return result
    except Exception as exc:
        raise RuntimeError(f"Failed to sample table {table_name}: {exc}")
