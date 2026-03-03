from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse


def _prepare_explain_sql(sql: str) -> str:
    converted = re.sub(r"(?i)\border\s+by\s+\$\{[^}]+\}", "ORDER BY 1", sql)
    converted = re.sub(r"(?i)\border\s+by\s+\?", "ORDER BY 1", converted)
    converted = re.sub(r"(?i)\border\s+by\s+#\{[^}]+\}", "ORDER BY 1", converted)
    converted = re.sub(r"#\{[^}]+\}", "NULL", converted)
    converted = re.sub(r"\?", "NULL", converted)
    converted = re.sub(r"\$\{[^}]+\}", "NULL", converted)
    converted = re.sub(r"(?i)\bselect\s+from\b", "SELECT * FROM", converted)
    converted = re.sub(r"(?i)\bfrom\s+([a-zA-Z0-9_.`\"]+)\s+and\b", r"FROM \1 WHERE", converted)
    converted = re.sub(r"(?i)\bwhere\s+and\b", "WHERE", converted)
    converted = re.sub(r"</?[^>]+>", " ", converted)
    return " ".join(converted.split())


def _extract_tables(sql: str) -> list[str]:
    pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z0-9_.`\"]+)", flags=re.IGNORECASE)
    names: list[str] = []
    for raw in pattern.findall(sql):
        candidate = raw.strip().strip('"').strip("`")
        if "." in candidate:
            candidate = candidate.split(".")[-1].strip('"').strip("`")
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _parse_mysql_dsn(dsn: str) -> dict[str, Any]:
    parsed = urlparse(str(dsn or ""))
    if parsed.scheme.lower() != "mysql":
        raise ValueError("mysql dsn must start with mysql://")
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("mysql dsn must include database name")
    query = {key: value for key, value in parse_qsl(parsed.query, keep_blank_values=True)}
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": int(parsed.port or 3306),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
        "charset": query.get("charset") or "utf8mb4",
        "query": query,
    }


def _build_connect_kwargs(dsn: str) -> dict[str, Any]:
    parsed = _parse_mysql_dsn(dsn)
    kwargs: dict[str, Any] = {
        "host": parsed["host"],
        "port": parsed["port"],
        "user": parsed["user"],
        "password": parsed["password"],
        "database": parsed["database"],
        "charset": parsed["charset"],
    }
    for key in ("ssl_disabled", "ssl_verify_cert", "ssl_verify_identity"):
        if key in parsed["query"]:
            raw = str(parsed["query"][key]).strip().lower()
            kwargs[key] = raw in {"1", "true", "yes", "on"}
    return kwargs


def _get_sql_connect() -> tuple[Any | None, str | None]:
    try:
        import pymysql  # type: ignore

        return pymysql.connect, "pymysql"
    except Exception:
        pass

    try:
        import mysql.connector  # type: ignore

        return mysql.connector.connect, "mysql-connector"
    except Exception:
        return None, None


def _quote_identifier(value: str) -> str:
    return "`" + str(value or "").replace("`", "``") + "`"


def _set_timeout(cur: Any, timeout_ms: int) -> None:
    cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {max(1, int(timeout_ms))}")


def _normalize_plan_lines(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    return [json.dumps(raw, ensure_ascii=False)]


def _extract_query_cost(raw: Any) -> float | None:
    payload = raw
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return None

    def visit(node: Any) -> float | None:
        if isinstance(node, dict):
            if "estimated_total_cost" in node:
                try:
                    return float(node["estimated_total_cost"])
                except Exception:
                    return None
            cost_info = node.get("cost_info")
            if isinstance(cost_info, dict) and "query_cost" in cost_info:
                try:
                    return float(cost_info["query_cost"])
                except Exception:
                    return None
            for value in node.values():
                found = visit(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = visit(value)
                if found is not None:
                    return found
        return None

    return visit(payload)


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    dsn = (config.get("db", {}) or {}).get("dsn")
    if not dsn:
        return {"name": "db", "enabled": True, "ok": False, "error": "db.dsn not set", "reason_code": "PREFLIGHT_DB_UNREACHABLE"}
    connect, _ = _get_sql_connect()
    if connect is None:
        return {"name": "db", "enabled": True, "ok": False, "error": "db driver not installed", "reason_code": "PREFLIGHT_DB_UNREACHABLE"}
    timeout = max(1, int((config.get("db", {}) or {}).get("statement_timeout_ms", 3000)))
    try:
        with connect(**_build_connect_kwargs(str(dsn))) as conn:
            with conn.cursor() as cur:
                _set_timeout(cur, timeout)
                cur.execute("SELECT 1")
                _ = cur.fetchone()
        return {"name": "db", "enabled": True, "ok": True}
    except Exception as exc:
        return {"name": "db", "enabled": True, "ok": False, "error": str(exc), "reason_code": "PREFLIGHT_DB_UNREACHABLE"}


def _collect_metadata(config: dict[str, Any], sql: str) -> dict[str, Any]:
    db_cfg = config.get("db", {})
    dsn = db_cfg.get("dsn")
    if not dsn:
        return {"enabled": False, "reason": "dsn_not_set"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"enabled": False, "reason": "db_driver_not_installed"}

    tables = _extract_tables(sql)
    dsn_parts = _parse_mysql_dsn(str(dsn))
    database = str(db_cfg.get("schema") or dsn_parts["database"])
    if not tables:
        return {"enabled": True, "ok": True, "schema": database, "tables": [], "indexes": [], "tableStats": [], "columns": []}

    timeout = max(1, int(db_cfg.get("statement_timeout_ms", 3000)))
    placeholders = ", ".join(["%s"] * len(tables))
    indexes: list[dict[str, Any]] = []
    try:
        with connect(**_build_connect_kwargs(str(dsn))) as conn:
            with conn.cursor() as cur:
                _set_timeout(cur, timeout)
                for table in tables:
                    cur.execute(f"SHOW INDEX FROM {_quote_identifier(table)} FROM {_quote_identifier(database)}")
                    for row in cur.fetchall():
                        key_name = row[2] if len(row) > 2 else ""
                        column_name = row[4] if len(row) > 4 else ""
                        indexes.append(
                            {
                                "table": table,
                                "index": key_name,
                                "definition": f"INDEX {key_name} ({column_name})",
                            }
                        )

                cur.execute(
                    (
                        "SELECT table_name, table_rows "
                        "FROM information_schema.tables "
                        "WHERE table_schema = %s "
                        f"AND table_name IN ({placeholders}) "
                        "ORDER BY table_name"
                    ),
                    [database, *tables],
                )
                table_stats = [
                    {"table": row[0], "estimatedRows": int(row[1] or 0)}
                    for row in cur.fetchall()
                ]

                cur.execute(
                    (
                        "SELECT table_name, column_name, data_type, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_schema = %s "
                        f"AND table_name IN ({placeholders}) "
                        "ORDER BY table_name, ordinal_position"
                    ),
                    [database, *tables],
                )
                columns = [
                    {"table": row[0], "column": row[1], "dataType": row[2], "isNullable": str(row[3]).upper() == "YES"}
                    for row in cur.fetchall()
                ]
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc), "tables": tables, "schema": database}

    return {
        "enabled": True,
        "ok": True,
        "driver": driver,
        "schema": database,
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
    timeout = max(1, int(db_cfg.get("statement_timeout_ms", 3000)))
    try:
        with connect(**_build_connect_kwargs(str(dsn))) as conn:
            with conn.cursor() as cur:
                _set_timeout(cur, timeout)
                cur.execute(f"EXPLAIN FORMAT=JSON {prepared_sql}")
                row = cur.fetchone()
                plan_raw = row[0] if row else "{}"
    except Exception as exc:
        return {"enabled": True, "ok": False, "error": str(exc)}

    return {
        "enabled": True,
        "ok": True,
        "driver": driver,
        "planLines": _normalize_plan_lines(plan_raw),
        "queryCost": _extract_query_cost(plan_raw),
    }


def collect_sql_evidence(config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
    explain = _collect_explain(config, sql)
    meta = _collect_metadata(config, sql)

    evidence: dict[str, Any] = {"dbType": "mysql"}
    if meta.get("enabled") and meta.get("ok"):
        evidence["driver"] = meta.get("driver")
        evidence["schema"] = meta.get("schema")
        evidence["tables"] = meta.get("tables", [])
        evidence["indexes"] = meta.get("indexes", [])
        evidence["tableStats"] = meta.get("tableStats", [])
        evidence["columns"] = meta.get("columns", [])
    elif meta.get("enabled") and not meta.get("ok"):
        evidence["metadataError"] = meta.get("error")
        evidence["schema"] = meta.get("schema")
        evidence["tables"] = meta.get("tables", [])
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

    plan_lines = list(explain.get("planLines", []))
    query_cost = explain.get("queryCost")
    evidence["collectionMode"] = "DB_CONNECTED"
    evidence["planLines"] = plan_lines[:20]
    if query_cost is not None:
        evidence["planCost"] = query_cost
    summary = f"query_cost={query_cost}" if query_cost is not None else (plan_lines[0] if plan_lines else "json explain")
    return evidence, {"summary": summary, "lineCount": len(plan_lines)}
