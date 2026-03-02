from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ...io_utils import write_json


def _prepare_executable_sql(sql: str) -> tuple[str, str | None]:
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
    normalized = " ".join(converted.split())
    if not normalized:
        return "", "empty_sql_after_prepare"
    if re.search(r"(?i)\bselect\s+from\b", normalized):
        return "", "select_missing_projection_after_prepare"
    if re.search(r"(?i)\b(from|where)\s+and\b", normalized):
        return "", "dangling_and_after_prepare"
    return normalized, None


def _is_connectivity_error(msg: str) -> bool:
    text = str(msg).lower()
    markers = [
        "connection to server",
        "could not connect",
        "connection refused",
        "operation not permitted",
        "network is unreachable",
        "timeout expired",
    ]
    return any(m in text for m in markers)


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


def _extract_plan(raw: Any) -> dict[str, Any]:
    payload = raw
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return {}
    if isinstance(payload, list) and payload:
        head = payload[0]
        return head.get("Plan", {}) if isinstance(head, dict) else {}
    if isinstance(payload, dict):
        return payload.get("Plan", {})
    return {}


def compare_plan(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    validate_cfg = config.get("validate", {})
    if not bool(validate_cfg.get("plan_compare_enabled", True)):
        return {"checked": False, "reason": "plan_compare_disabled", "reasonCategory": "PLAN_COMPARE_DISABLED"}

    dsn = (config.get("db", {}) or {}).get("dsn")
    if not dsn:
        return {"checked": False, "reason": "dsn_not_set", "reasonCategory": "NO_DSN"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"checked": False, "reason": "db_driver_not_installed", "reasonCategory": "DRIVER_NOT_INSTALLED"}

    o_sql, o_err = _prepare_executable_sql(original_sql)
    r_sql, r_err = _prepare_executable_sql(rewritten_sql)
    if o_err or r_err:
        return {
            "checked": False,
            "reason": "sql_prepare_failed",
            "reasonCategory": "SQL_PREPARE_FAILED",
            "error": f"original={o_err or 'ok'}, rewritten={r_err or 'ok'}",
            "improved": None,
            "reasonCodes": [],
        }
    timeout = max(1, int((config.get("db", {}) or {}).get("statement_timeout_ms", 3000)))
    try:
        with connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {timeout}")
                cur.execute(f"EXPLAIN (FORMAT JSON) {o_sql}")
                before_raw = cur.fetchone()[0]
                cur.execute(f"EXPLAIN (FORMAT JSON) {r_sql}")
                after_raw = cur.fetchone()[0]
    except Exception as exc:
        if bool(validate_cfg.get("allow_db_unreachable_fallback", False)) and _is_connectivity_error(str(exc)):
            return {
                "checked": False,
                "reason": "db_unreachable",
                "reasonCategory": "DB_UNREACHABLE",
                "error": str(exc),
                "improved": None,
                "reasonCodes": [],
            }
        return {
            "checked": True,
            "error": str(exc),
            "improved": None,
            "reasonCodes": [],
            "reasonCategory": "EXPLAIN_ERROR",
        }

    before_plan = _extract_plan(before_raw)
    after_plan = _extract_plan(after_raw)
    before_cost = before_plan.get("Total Cost")
    after_cost = after_plan.get("Total Cost")

    reason_codes: list[str] = []
    improved = None
    if isinstance(before_cost, (int, float)) and isinstance(after_cost, (int, float)):
        threshold = float(before_cost) * (1.0 - float((config.get("policy", {}) or {}).get("cost_threshold_pct", 0)) / 100.0)
        if float(after_cost) < threshold:
            improved = True
            reason_codes.append("TOTAL_COST_REDUCED")
        else:
            improved = False
            reason_codes.append("TOTAL_COST_NOT_REDUCED")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    before_path = evidence_dir / "original.explain.json"
    after_path = evidence_dir / "rewritten.explain.json"
    write_json(before_path, {"explain": before_raw})
    write_json(after_path, {"explain": after_raw})

    return {
        "checked": True,
        "method": "sql_explain_json_compare",
        "driver": driver,
        "beforeSummary": {"totalCost": before_cost},
        "afterSummary": {"totalCost": after_cost},
        "reasonCodes": reason_codes,
        "improved": improved,
        "evidenceRefs": [str(before_path), str(after_path)],
    }


def compare_semantics(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    dsn = (config.get("db", {}) or {}).get("dsn")
    if not dsn:
        return {"checked": False, "reason": "dsn_not_set"}

    connect, driver = _get_sql_connect()
    if connect is None:
        return {"checked": False, "reason": "db_driver_not_installed"}

    timeout = max(1, int((config.get("db", {}) or {}).get("statement_timeout_ms", 3000)))
    o_sql, o_err = _prepare_executable_sql(original_sql)
    r_sql, r_err = _prepare_executable_sql(rewritten_sql)
    if o_err or r_err:
        return {
            "checked": False,
            "reason": "sql_prepare_failed",
            "reasonCategory": "SQL_PREPARE_FAILED",
            "error": f"original={o_err or 'ok'}, rewritten={r_err or 'ok'}",
            "rowCount": {"status": "SKIPPED", "reason": "sql_prepare_failed"},
        }
    try:
        with connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {timeout}")
                cur.execute(f"SELECT COUNT(*)::bigint FROM ({o_sql}) q")
                before_count = int(cur.fetchone()[0])
                cur.execute(f"SELECT COUNT(*)::bigint FROM ({r_sql}) q")
                after_count = int(cur.fetchone()[0])
    except Exception as exc:
        if bool((config.get("validate", {}) or {}).get("allow_db_unreachable_fallback", False)) and _is_connectivity_error(str(exc)):
            return {
                "checked": False,
                "reason": "db_unreachable",
                "reasonCategory": "DB_UNREACHABLE",
                "rowCount": {"status": "SKIPPED", "reason": "db_unreachable"},
            }
        return {"checked": True, "error": str(exc), "rowCount": {"status": "ERROR", "error": str(exc)}}

    result = {
        "checked": True,
        "method": "sql_semantic_compare_v1",
        "driver": driver,
        "rowCount": {
            "status": "MATCH" if before_count == after_count else "MISMATCH",
            "before": before_count,
            "after": after_count,
        },
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    eq_path = evidence_dir / "equivalence.json"
    write_json(eq_path, result)
    result["evidenceRefs"] = [str(eq_path)]
    return result
