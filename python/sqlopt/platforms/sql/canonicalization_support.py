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
SELECT_DIRECT_RE = re.compile(r"^\s*select\s+(?P<select>.+?)\s+(?P<from>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)

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
_TRAILING_ALIAS_RE = re.compile(r"\s+as\s+[a-z_][a-z0-9_]*\s*$|\s+[a-z_][a-z0-9_]*\s*$", flags=re.IGNORECASE)


def normalize_sql(value: str) -> str:
    return " ".join(str(value or "").split())


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


def redundant_subquery_blockers(inner_from: str) -> list[str]:
    normalized = normalize_sql(inner_from)
    blockers: list[str] = []
    for pattern, code in _BLOCKING_SUBQUERY_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            blockers.append(code)
    return blockers


def extract_from_suffix(sql: str) -> str | None:
    match = SELECT_DIRECT_RE.match(normalize_sql(sql))
    if match is None:
        return None
    return normalize_sql(match.group("from"))
