from __future__ import annotations

import re
from typing import Any


def _prepare_explain_sql(sql: str) -> str:
    converted = re.sub(r"(?i)\border\s+by\s+\$\{[^}]+\}", "ORDER BY 1", sql)
    converted = re.sub(r"(?i)\border\s+by\s+\?", "ORDER BY 1", converted)
    converted = re.sub(r"(?i)\border\s+by\s+#\{[^}]+\}", "ORDER BY 1", converted)
    converted = re.sub(r"#\{[^}]+\}", "NULL", converted)
    converted = re.sub(r"\?", "NULL", converted)
    converted = re.sub(r"\$\{[^}]+\}", "NULL", converted)
    converted = re.sub(r"(?i)\bselect\s+from\b", "SELECT * FROM", converted)
    converted = re.sub(r"(?i)\bfrom\s+([a-zA-Z0-9_.\"]+)\s+and\b", r"FROM \1 WHERE", converted)
    converted = re.sub(r"(?i)\bwhere\s+and\b", "WHERE", converted)
    converted = re.sub(r"</?[^>]+>", " ", converted)
    return converted


def _extract_tables(sql: str) -> list[str]:
    pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z0-9_.\"]+)", flags=re.IGNORECASE)
    names: list[str] = []
    for raw in pattern.findall(sql):
        candidate = raw.strip().strip('"')
        if "." in candidate:
            candidate = candidate.split(".")[-1].strip('"')
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _get_sql_connect() -> tuple[Any | None, str | None]:
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


def _collect_metadata(config: dict[str, Any], sql: str) -> dict[str, Any]:
    db_cfg = config.get("db", {})
    dsn = db_cfg.get("dsn")
    if not dsn:
        return {"enabled": False, "reason": "dsn_not_set"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"enabled": False, "reason": "db_driver_not_installed"}

    tables = _extract_tables(sql)
    if not tables:
        return {"enabled": True, "ok": True, "tables": [], "indexes": [], "tableStats": [], "columns": []}

    schema = db_cfg.get("schema")
    statement_timeout_ms = int(db_cfg.get("statement_timeout_ms", 3000))
    try:
        with connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {max(1, statement_timeout_ms)}")
                if not schema:
                    cur.execute("SELECT current_schema()")
                    row = cur.fetchone()
                    schema = row[0] if row else "public"

                cur.execute(
                    """
                    SELECT tablename, indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = %s
                      AND tablename = ANY(%s)
                    ORDER BY tablename, indexname
                    """,
                    (schema, tables),
                )
                indexes = [{"table": r[0], "index": r[1], "definition": r[2]} for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT c.relname, c.reltuples::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s
                      AND c.relkind = 'r'
                      AND c.relname = ANY(%s)
                    ORDER BY c.relname
                    """,
                    (schema, tables),
                )
                table_stats = [{"table": r[0], "estimatedRows": int(r[1])} for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT table_name, column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = ANY(%s)
                    ORDER BY table_name, ordinal_position
                    """,
                    (schema, tables),
                )
                columns = [
                    {"table": r[0], "column": r[1], "dataType": r[2], "isNullable": r[3] == "YES"}
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc), "tables": tables}

    return {
        "enabled": True,
        "ok": True,
        "driver": driver,
        "schema": schema,
        "tables": tables,
        "indexes": indexes[:50],
        "tableStats": table_stats,
        "columns": columns[:200],
    }


def _collect_explain(config: dict[str, Any], sql: str) -> dict[str, Any]:
    db_cfg = config.get("db", {})
    dsn = db_cfg.get("dsn")
    if not dsn:
        return {"enabled": False, "reason": "dsn_not_set"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"enabled": False, "reason": "db_driver_not_installed"}

    prepared_sql = _prepare_explain_sql(sql)
    explain_prefix = "EXPLAIN (FORMAT TEXT)"
    if bool(db_cfg.get("allow_explain_analyze", False)):
        explain_prefix = "EXPLAIN (ANALYZE TRUE, FORMAT TEXT)"

    statement_timeout_ms = int(db_cfg.get("statement_timeout_ms", 3000))
    try:
        with connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {max(1, statement_timeout_ms)}")
                cur.execute(f"{explain_prefix} {prepared_sql}")
                rows = cur.fetchall()
                plan_lines = [str(row[0]) for row in rows]
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)}

    return {"enabled": True, "ok": True, "driver": driver, "planLines": plan_lines}


def collect_sql_evidence(config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
    explain = _collect_explain(config, sql)
    meta = _collect_metadata(config, sql)

    platform = str((config.get("db", {}) or {}).get("platform", "sql"))
    evidence: dict[str, Any] = {"dbType": platform}
    if meta.get("enabled") and meta.get("ok"):
        evidence["driver"] = meta.get("driver")
        evidence["schema"] = meta.get("schema")
        evidence["tables"] = meta.get("tables", [])
        evidence["indexes"] = meta.get("indexes", [])
        evidence["tableStats"] = meta.get("tableStats", [])
        evidence["columns"] = meta.get("columns", [])
    elif meta.get("enabled") and not meta.get("ok"):
        evidence["metadataError"] = meta.get("error")
    else:
        evidence["metadataReason"] = meta.get("reason")

    if not explain.get("enabled"):
        evidence["collectionMode"] = "STATIC_ONLY"
        evidence["explainReason"] = explain.get("reason")
        return evidence, {"summary": "EXPLAIN skipped", "reason": explain.get("reason")}

    if not explain.get("ok"):
        evidence["collectionMode"] = "DB_CONNECTED"
        evidence["explainError"] = explain.get("error")
        return evidence, {"summary": "EXPLAIN failed", "error": explain.get("error")}

    plan_lines = explain.get("planLines", [])
    evidence["collectionMode"] = "DB_CONNECTED"
    evidence["planLines"] = plan_lines[:20]
    return evidence, {"summary": plan_lines[0] if plan_lines else "empty plan", "lineCount": len(plan_lines)}
