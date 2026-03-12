from __future__ import annotations

import re
from typing import Any

from .canonicalization_models import CanonicalContext

COUNT_DIRECT_RE = re.compile(r"^\s*select\s+count\s*\(\s*(?P<arg>[^)]+)\s*\)\s+from\b", flags=re.IGNORECASE)
COUNT_DIRECT_SUFFIX_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*[^)]+\s*\)\s+(?P<from>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
COUNT_WRAPPER_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<arg>[^)]+)\s*\)\s+from\s*\((?P<inner>.+)\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
SELECT_WRAPPER_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(\s*select\s+(?P<inner_select>.+?)\s+(?P<inner_from>from\b.+)\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
GROUP_BY_WRAPPER_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(\s*select\s+(?P<inner_select>.+?)\s+(?P<inner_from>from\b.+?)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*(?P<outer_suffix>(?:order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
HAVING_WRAPPER_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(\s*select\s+(?P<inner_select>.+?)\s+(?P<inner_from>from\b.+?)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*(?P<outer_suffix>(?:order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
SELECT_DIRECT_RE = re.compile(r"^\s*select\s+(?P<select>.+?)\s+(?P<from>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)
DISTINCT_WRAPPER_RE = re.compile(
    r"^\s*select\s+distinct\s+(?P<outer_select>.+?)\s+from\s*\(\s*select\s+distinct\s+(?P<inner_select>.+?)\s+(?P<inner_from>from\b.+?)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*(?P<outer_suffix>(?:where\b|order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
DISTINCT_DIRECT_RE = re.compile(
    r"^\s*select\s+distinct\s+(?P<select>.+?)\s+(?P<from>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)

_BLOCKING_SUBQUERY_PATTERNS = (
    (r"\bdistinct\b", "DISTINCT_PRESENT"),
    (r"\bgroup\s+by\b", "GROUP_BY_PRESENT"),
    (r"\bhaving\b", "HAVING_PRESENT"),
    (r"\bunion\b", "UNION_PRESENT"),
    (r"\bover\s*\(", "WINDOW_PRESENT"),
    (r"\blimit\b", "LIMIT_PRESENT"),
    (r"\boffset\b", "OFFSET_PRESENT"),
    (r"\bfetch\b", "FETCH_PRESENT"),
)
_GROUP_BY_WRAPPER_BLOCKING_PATTERNS = (
    (r"\bdistinct\b", "DISTINCT_PRESENT"),
    (r"\bhaving\b", "HAVING_PRESENT"),
    (r"\bunion\b", "UNION_PRESENT"),
    (r"\bover\s*\(", "WINDOW_PRESENT"),
    (r"\blimit\b", "LIMIT_PRESENT"),
    (r"\boffset\b", "OFFSET_PRESENT"),
    (r"\bfetch\b", "FETCH_PRESENT"),
)
_TRAILING_ALIAS_RE = re.compile(r"\s+as\s+[a-z_][a-z0-9_]*\s*$|\s+[a-z_][a-z0-9_]*\s*$", flags=re.IGNORECASE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", flags=re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n\r]*")
_REDUNDANT_ALIAS_RE = re.compile(
    r"^\s*(?P<expr>[a-z_][a-z0-9_\.]*)\s+(?:as\s+)?(?P<alias>[a-z_][a-z0-9_]*)\s*$",
    flags=re.IGNORECASE,
)
_REDUNDANT_FROM_ALIAS_RE = re.compile(
    r"^\s*from\s+(?P<table>[a-z_][a-z0-9_\.]*)(?:\s+(?:as\s+)?(?P<alias>[a-z_][a-z0-9_]*))(?P<suffix>.*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
_FROM_ALIAS_RESERVED = {
    "where",
    "order",
    "limit",
    "offset",
    "fetch",
    "group",
    "having",
    "join",
    "left",
    "right",
    "inner",
    "outer",
    "cross",
    "union",
    "on",
}


def normalize_sql(value: str) -> str:
    return " ".join(str(value or "").split())


def strip_sql_comments(value: str) -> str:
    text = str(value or "")
    without_block = _BLOCK_COMMENT_RE.sub(" ", text)
    without_line = _LINE_COMMENT_RE.sub(" ", without_block)
    return without_line


def fingerprint_strength(semantics: dict[str, Any]) -> str:
    for row in semantics.get("evidenceRefObjects") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "").strip().upper() != "DB_FINGERPRINT":
            continue
        match_strength = str(row.get("match_strength") or "").strip().upper()
        if match_strength:
            return match_strength
    key_status = str(((semantics.get("keySetHash") or {}).get("status") or "")).strip().upper()
    sample_status = str(((semantics.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    if key_status == "MATCH":
        return "EXACT"
    if sample_status == "MATCH":
        return "PARTIAL"
    return "NONE"


def build_canonical_context(original_sql: str, rewritten_sql: str, semantics: dict[str, Any]) -> CanonicalContext:
    normalized_original_sql = normalize_sql(original_sql)
    normalized_rewritten_sql = normalize_sql(rewritten_sql)
    return CanonicalContext(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        normalized_original_sql=normalized_original_sql,
        normalized_rewritten_sql=normalized_rewritten_sql,
        semantics=semantics,
        row_count_status=str(((semantics.get("rowCount") or {}).get("status") or "")).strip().upper(),
        fingerprint_strength=fingerprint_strength(semantics),
    )


def strip_projection_alias(expr: str) -> str:
    return normalize_sql(_TRAILING_ALIAS_RE.sub("", str(expr or "").strip()))


def split_select_list(select_text: str) -> list[str]:
    text = str(select_text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                parts.append(normalize_sql("".join(current)))
                current = []
                continue
        current.append(ch)
    if current:
        parts.append(normalize_sql("".join(current)))
    return [part for part in parts if part]


def strip_redundant_projection_alias(expr: str) -> str:
    normalized = normalize_sql(expr)
    match = _REDUNDANT_ALIAS_RE.match(normalized)
    if match is None:
        return normalized
    base_expr = normalize_sql(match.group("expr"))
    alias = normalize_sql(match.group("alias"))
    if base_expr.rsplit(".", 1)[-1].lower() != alias.lower():
        return normalized
    return base_expr


def cleanup_redundant_select_aliases(select_text: str) -> tuple[str, bool]:
    parts = split_select_list(select_text)
    if not parts:
        return normalize_sql(select_text), False
    cleaned_parts = [strip_redundant_projection_alias(part) for part in parts]
    changed = any(normalize_sql(before) != normalize_sql(after) for before, after in zip(parts, cleaned_parts))
    return ", ".join(cleaned_parts), changed


def cleanup_redundant_from_alias(from_suffix: str, *, select_text: str | None = None) -> tuple[str, bool]:
    normalized = normalize_sql(from_suffix)
    match = _REDUNDANT_FROM_ALIAS_RE.match(normalized)
    if match is None:
        return normalized, False
    table_name = normalize_sql(match.group("table"))
    alias = normalize_sql(match.group("alias"))
    suffix = normalize_sql(match.group("suffix") or "")
    if alias.lower() in _FROM_ALIAS_RESERVED:
        return normalized, False
    if suffix and not (
        suffix.lower().startswith("where ")
        or suffix.lower().startswith("order by ")
        or suffix.lower().startswith("limit ")
        or suffix.lower().startswith("offset ")
        or suffix.lower().startswith("fetch ")
        or suffix.startswith("<")
    ):
        return normalized, False
    alias_ref = f"{alias.lower()}."
    if alias_ref in normalize_sql(select_text or "").lower():
        return normalized, False
    if alias_ref in suffix.lower():
        return normalized, False
    cleaned = normalize_sql(f"FROM {table_name} {suffix}").strip()
    return cleaned or normalized, True


def redundant_subquery_blockers(inner_from: str) -> list[str]:
    normalized = normalize_sql(inner_from)
    blockers: list[str] = []
    for pattern, code in _BLOCKING_SUBQUERY_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            blockers.append(code)
    return blockers


def redundant_groupby_wrapper_blockers(inner_from: str) -> list[str]:
    normalized = normalize_sql(inner_from)
    blockers: list[str] = []
    if not re.search(r"\bgroup\s+by\b", normalized, flags=re.IGNORECASE):
        blockers.append("GROUP_BY_MISSING")
    for pattern, code in _GROUP_BY_WRAPPER_BLOCKING_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            blockers.append(code)
    return blockers


def redundant_having_wrapper_blockers(inner_from: str) -> list[str]:
    normalized = normalize_sql(inner_from)
    blockers: list[str] = []
    if not re.search(r"\bgroup\s+by\b", normalized, flags=re.IGNORECASE):
        blockers.append("GROUP_BY_MISSING")
    if not re.search(r"\bhaving\b", normalized, flags=re.IGNORECASE):
        blockers.append("HAVING_MISSING")
    for pattern, code in (
        (r"\bdistinct\b", "DISTINCT_PRESENT"),
        (r"\bunion\b", "UNION_PRESENT"),
        (r"\bover\s*\(", "WINDOW_PRESENT"),
        (r"\blimit\b", "LIMIT_PRESENT"),
        (r"\boffset\b", "OFFSET_PRESENT"),
        (r"\bfetch\b", "FETCH_PRESENT"),
    ):
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            blockers.append(code)
    return blockers


def extract_from_suffix(sql: str) -> str | None:
    match = SELECT_DIRECT_RE.match(normalize_sql(sql))
    if match is None:
        return None
    return normalize_sql(match.group("from"))
