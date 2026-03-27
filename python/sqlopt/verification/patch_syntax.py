from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .patch_artifact import PatchArtifactResult, materialize_patch_artifact

_PLACEHOLDER_RE = re.compile(r"(?:#|\$)\{[^}]+\}")
_TRAILING_SQL_TOKENS = (
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP BY",
    "ORDER BY",
    "HAVING",
    "JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "INNER JOIN",
    "FULL JOIN",
    "CROSS JOIN",
    "ON",
    "AND",
    "OR",
    "SET",
    "VALUES",
    "INTO",
    "LIMIT",
    "OFFSET",
    "UNION",
)
_START_KEYWORDS = ("SELECT", "UPDATE", "DELETE", "INSERT", "WITH")


@dataclass(frozen=True)
class PatchSyntaxResult:
    ok: bool
    xml_parse_ok: bool
    render_ok: bool
    sql_parse_ok: bool
    rendered_sql_present: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "xmlParseOk": self.xml_parse_ok,
            "renderOk": self.render_ok,
            "sqlParseOk": self.sql_parse_ok,
            "renderedSqlPresent": self.rendered_sql_present,
            "reasonCode": self.reason_code,
        }


def _normalize_sql_for_validation(sql: str) -> str:
    collapsed = " ".join(str(sql or "").split())
    return _PLACEHOLDER_RE.sub("__placeholder__", collapsed)


def _has_balanced_quotes_and_parentheses(sql: str) -> bool:
    depth = 0
    in_single_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'":
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    return False
        index += 1
    return (not in_single_quote) and depth == 0


def _starts_like_sql_statement(sql: str) -> bool:
    upper = sql.upper()
    return any(upper.startswith(keyword) for keyword in _START_KEYWORDS)


def _has_required_statement_shape(sql: str) -> bool:
    upper = sql.upper()
    if upper.startswith("UPDATE "):
        return " SET " in upper
    if upper.startswith("DELETE "):
        return " FROM " in upper
    if upper.startswith("INSERT "):
        return " INTO " in upper and " VALUES" in upper
    if upper.startswith("WITH "):
        return any(f" {keyword} " in upper for keyword in ("SELECT", "UPDATE", "DELETE", "INSERT"))
    return True


def _has_trailing_incomplete_clause(sql: str) -> bool:
    upper = sql.upper().rstrip(" ,")
    return any(upper.endswith(token) for token in _TRAILING_SQL_TOKENS)


def _is_obviously_valid_sql(sql: str) -> bool:
    normalized = _normalize_sql_for_validation(sql)
    if not normalized:
        return False
    if not _starts_like_sql_statement(normalized):
        return False
    if not _has_balanced_quotes_and_parentheses(normalized):
        return False
    if not _has_required_statement_shape(normalized):
        return False
    if _has_trailing_incomplete_clause(normalized):
        return False
    return True


def verify_patch_syntax(
    *,
    sql_unit: dict[str, Any],
    patch_target: dict[str, Any],
    patch_text: str,
    replay_result: Any,
    artifact: PatchArtifactResult | None = None,
) -> PatchSyntaxResult:
    artifact_result = artifact
    if artifact_result is None and str(patch_text or "").strip():
        artifact_result = materialize_patch_artifact(sql_unit=sql_unit, patch_text=patch_text)
    if getattr(replay_result, "matches_target", False) is not True:
        sql_present = bool(getattr(replay_result, "normalized_rendered_sql", None))
        return PatchSyntaxResult(
            ok=False,
            xml_parse_ok=bool(getattr(artifact_result, "xml_parse_ok", False)),
            render_ok=sql_present,
            sql_parse_ok=_is_obviously_valid_sql(str(getattr(replay_result, "rendered_sql", None) or "")) if sql_present else False,
            rendered_sql_present=sql_present,
            reason_code=str(
                getattr(replay_result, "drift_reason", None)
                or getattr(artifact_result, "reason_code", None)
                or "PATCH_TARGET_DRIFT"
            ),
        )
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    xml_parse_ok = bool(getattr(artifact_result, "xml_parse_ok", False))
    if artifact_result is None and xml_path.exists():
        try:
            ET.parse(xml_path)
            xml_parse_ok = True
        except Exception:
            xml_parse_ok = False
    rendered_sql_present = bool(getattr(replay_result, "normalized_rendered_sql", None) or str(patch_target.get("targetSql") or "").strip())
    render_ok = rendered_sql_present
    rendered_sql = str(
        getattr(replay_result, "rendered_sql", None)
        or getattr(replay_result, "normalized_rendered_sql", None)
        or patch_target.get("targetSql")
        or ""
    )
    sql_parse_ok = _is_obviously_valid_sql(rendered_sql) if rendered_sql_present else False
    ok = xml_parse_ok and render_ok and sql_parse_ok and bool(str(patch_text or "").strip())
    return PatchSyntaxResult(
        ok=ok,
        xml_parse_ok=xml_parse_ok,
        render_ok=render_ok,
        sql_parse_ok=sql_parse_ok,
        rendered_sql_present=rendered_sql_present,
        reason_code=None
        if ok
        else str(
            getattr(artifact_result, "reason_code", None)
            or ("PATCH_SQL_PARSE_FAILED" if sql_parse_ok is False and rendered_sql_present else "PATCH_SYNTAX_INVALID")
        ),
    )
