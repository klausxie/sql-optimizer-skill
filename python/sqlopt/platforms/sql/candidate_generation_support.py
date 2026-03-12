from __future__ import annotations

import re
from typing import Any

from .canonicalization_support import (
    DISTINCT_WRAPPER_RE,
    GROUP_BY_WRAPPER_RE,
    HAVING_WRAPPER_RE,
    SELECT_DIRECT_RE,
    SELECT_WRAPPER_RE,
    cleanup_redundant_from_alias,
    cleanup_redundant_select_aliases,
    normalize_sql,
    redundant_groupby_wrapper_blockers,
    redundant_having_wrapper_blockers,
    redundant_subquery_blockers,
)
from .cte_analysis import analyze_simple_inline_cte

AGGREGATIONISH_SQL_RE = re.compile(
    r"\bgroup\s+by\b|\bhaving\b|\bover\s*\(|\bunion\b|^\s*with\b|\bselect\s+distinct\b|\bselect\b.+\bfrom\s*\(\s*select\b",
    flags=re.IGNORECASE | re.DOTALL,
)
WHERE_RE = re.compile(r"\bwhere\b", flags=re.IGNORECASE)
LIMIT_RE = re.compile(r"\blimit\b", flags=re.IGNORECASE)
WINDOW_RE = re.compile(r"\bover\s*\(", flags=re.IGNORECASE)
DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)
PAGED_RE = re.compile(r"\border\s+by\b.*\blimit\b", flags=re.IGNORECASE | re.DOTALL)
SIMPLE_WHERE_SQL_RE = re.compile(
    r"^\s*(?P<prefix>select\b.+?\bfrom\b.+?)\s+where\s+(?P<predicate>.+?)(?:\s+(?P<suffix>order\s+by\b.+|limit\b.+|offset\b.+|fetch\b.+))?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
OUTER_WRAPPER_PREFIX_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(",
    flags=re.IGNORECASE | re.DOTALL,
)
OUTER_ALIAS_SUFFIX_RE = re.compile(
    r"^\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*(?P<outer_suffix>(?:where\b|order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
STRUCTURAL_FALLBACK_CUES = (
    "redundant outer query",
    "unnecessary subquery wrapper",
    "remove the unnecessary subquery wrapper",
    "remove unnecessary subquery wrapper",
    "remove redundant subquery wrapper",
    "removes the redundant subquery wrapper",
    "removes the redundant subquery",
    "eliminates the redundant subquery",
    "eliminating unnecessary cte",
    "unnecessary cte",
    "redundant cte",
    "cte is redundant",
    "remove the cte",
)
COUNT_WRAPPER_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
COUNT_DIRECT_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
COUNT_WRAPPER_BLOCKERS = re.compile(
    r"\bdistinct\b|\bgroup\s+by\b|\bhaving\b|\bunion\b|\bover\s*\(|\blimit\b|\boffset\b|\bfetch\b",
    flags=re.IGNORECASE | re.DOTALL,
)


def normalized_sql_eq(left: str | None, right: str | None) -> bool:
    return normalize_sql(left or "").lower() == normalize_sql(right or "").lower()


def _split_top_level_and(predicate: str) -> list[str] | None:
    text = str(predicate or "").strip()
    if not text:
        return []
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    lower = text.lower()
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and lower.startswith(" and ", i):
            part = normalize_sql("".join(buf))
            if not part:
                return None
            parts.append(part)
            buf = []
            i += 5
            continue
        buf.append(ch)
        i += 1
    tail = normalize_sql("".join(buf))
    if not tail:
        return None
    parts.append(tail)
    if any(re.search(r"\bor\b", part, flags=re.IGNORECASE) for part in parts):
        return None
    return parts


def simple_where_predicate_signature(sql: str) -> tuple[str, tuple[str, ...], str] | None:
    normalized = normalize_sql(sql)
    match = SIMPLE_WHERE_SQL_RE.match(normalized)
    if match is None:
        return None
    predicate = str(match.group("predicate") or "").strip()
    if not predicate:
        return None
    parts = _split_top_level_and(predicate)
    if parts is None or len(parts) < 2:
        return None
    prefix = normalize_sql(match.group("prefix"))
    suffix = normalize_sql(match.group("suffix") or "")
    return prefix.lower(), tuple(sorted(part.lower() for part in parts)), suffix.lower()


def render_flattened_wrapper_sql(prefix: str, select_list: str, from_suffix: str, outer_suffix: str | None) -> str:
    suffix = f" {normalize_sql(outer_suffix)}" if str(outer_suffix or "").strip() else ""
    return normalize_sql(f"{prefix} {normalize_sql(select_list)} {normalize_sql(from_suffix)}{suffix}")


def dynamic_filter_select_cleanup_sql(original_sql: str) -> str | None:
    normalized = normalize_sql(original_sql)
    direct_match = SELECT_DIRECT_RE.match(normalized)
    if direct_match is None or not WHERE_RE.search(normalized):
        return None
    cleaned_select, aliases_changed = cleanup_redundant_select_aliases(str(direct_match.group("select") or ""))
    if not aliases_changed:
        return None
    return normalize_sql(f"SELECT {cleaned_select} {direct_match.group('from')}")


def dynamic_filter_from_alias_cleanup_sql(original_sql: str) -> str | None:
    normalized = normalize_sql(original_sql)
    direct_match = SELECT_DIRECT_RE.match(normalized)
    if direct_match is None or not WHERE_RE.search(normalized):
        return None
    select_text = str(direct_match.group("select") or "")
    from_suffix = str(direct_match.group("from") or "")
    cleaned_from_suffix, changed = cleanup_redundant_from_alias(from_suffix, select_text=select_text)
    if not changed:
        return None
    return normalize_sql(f"SELECT {select_text} {cleaned_from_suffix}")


def find_matching_paren(text: str, start_idx: int) -> int:
    depth = 0
    for idx in range(start_idx, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def parse_simple_select_wrapper(sql: str) -> tuple[str | None, str | None, str | None]:
    normalized = normalize_sql(sql)
    prefix_match = OUTER_WRAPPER_PREFIX_RE.match(normalized)
    if prefix_match is None:
        return None, None, None
    outer_select = normalize_sql(prefix_match.group("outer_select"))
    open_paren_idx = prefix_match.end() - 1
    close_paren_idx = find_matching_paren(normalized, open_paren_idx)
    if close_paren_idx < 0:
        return None, None, None
    inner_sql = normalize_sql(normalized[open_paren_idx + 1 : close_paren_idx])
    inner_match = SELECT_DIRECT_RE.match(inner_sql)
    if inner_match is None:
        return None, None, None
    inner_select = normalize_sql(inner_match.group("select"))
    inner_from = normalize_sql(inner_match.group("from"))
    suffix_match = OUTER_ALIAS_SUFFIX_RE.match(normalized[close_paren_idx + 1 :])
    outer_suffix = normalize_sql((suffix_match.group("outer_suffix") if suffix_match else "") or "")
    return outer_select or None, inner_select or None, normalize_sql(f"{inner_from} {outer_suffix}").strip() or inner_from


def classify_blocked_shape(original_sql: str, sql_unit: dict[str, Any]) -> str:
    normalized = normalize_sql(original_sql)
    dynamic_features = {str(row).upper() for row in (sql_unit.get("dynamicFeatures") or [])}
    if WINDOW_RE.search(normalized):
        return "NO_SAFE_BASELINE_WINDOW"
    if "INCLUDE" in dynamic_features and PAGED_RE.search(normalized):
        return "NO_SAFE_BASELINE_DYNAMIC_PAGED_INCLUDE"
    return "NO_SAFE_BASELINE_SHAPE_MATCH"


def recover_candidates_from_shape(sql_key: str, original_sql: str) -> list[dict[str, Any]]:
    normalized_original = normalize_sql(original_sql)
    recovered: list[dict[str, Any]] = []

    count_wrapper_match = COUNT_WRAPPER_RE.match(normalized_original)
    if count_wrapper_match is not None:
        inner_sql = normalize_sql(count_wrapper_match.group("inner"))
        inner_match = SELECT_DIRECT_RE.match(inner_sql)
        count_expr = normalize_sql(count_wrapper_match.group("count_expr"))
        if inner_match is not None and count_expr in {"1", "*"}:
            inner_from = normalize_sql(inner_match.group("from"))
            if not COUNT_WRAPPER_BLOCKERS.search(inner_from):
                return [
                    {
                        "id": f"{sql_key}:llm:recovered_dynamic_count_wrapper",
                        "source": "llm",
                        "rewrittenSql": normalize_sql(f"SELECT COUNT(*) {inner_from}"),
                        "rewriteStrategy": "REMOVE_DYNAMIC_COUNT_WRAPPER_RECOVERED",
                        "semanticRisk": "low",
                        "confidence": "medium",
                    }
                ]

    cte = analyze_simple_inline_cte(normalized_original)
    if cte.present and cte.collapsible:
        return [
            {
                "id": f"{sql_key}:llm:recovered_cte",
                "source": "llm",
                "rewrittenSql": str(cte.inlined_sql or "").strip(),
                "rewriteStrategy": "INLINE_SIMPLE_CTE_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    distinct_match = DISTINCT_WRAPPER_RE.match(normalized_original)
    if distinct_match is not None and normalized_sql_eq(distinct_match.group("outer_select"), distinct_match.group("inner_select")):
        return [
            {
                "id": f"{sql_key}:llm:recovered_distinct_wrapper",
                "source": "llm",
                "rewrittenSql": render_flattened_wrapper_sql(
                    "SELECT DISTINCT",
                    distinct_match.group("inner_select"),
                    distinct_match.group("inner_from"),
                    distinct_match.group("outer_suffix"),
                ),
                "rewriteStrategy": "REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    having_match = HAVING_WRAPPER_RE.match(normalized_original)
    if having_match is not None and normalized_sql_eq(having_match.group("outer_select"), having_match.group("inner_select")):
        inner_from = str(having_match.group("inner_from") or "")
        if not redundant_having_wrapper_blockers(inner_from):
            return [
                {
                    "id": f"{sql_key}:llm:recovered_having_wrapper",
                    "source": "llm",
                    "rewrittenSql": render_flattened_wrapper_sql(
                        "SELECT",
                        having_match.group("inner_select"),
                        inner_from,
                        having_match.group("outer_suffix"),
                    ),
                    "rewriteStrategy": "REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED",
                    "semanticRisk": "low",
                    "confidence": "medium",
                }
            ]

    group_by_match = GROUP_BY_WRAPPER_RE.match(normalized_original)
    if group_by_match is not None and normalized_sql_eq(group_by_match.group("outer_select"), group_by_match.group("inner_select")):
        inner_from = str(group_by_match.group("inner_from") or "")
        if not redundant_groupby_wrapper_blockers(inner_from):
            return [
                {
                    "id": f"{sql_key}:llm:recovered_groupby_wrapper",
                    "source": "llm",
                    "rewrittenSql": render_flattened_wrapper_sql(
                        "SELECT",
                        group_by_match.group("inner_select"),
                        inner_from,
                        group_by_match.group("outer_suffix"),
                    ),
                    "rewriteStrategy": "REMOVE_REDUNDANT_GROUP_BY_WRAPPER_RECOVERED",
                    "semanticRisk": "low",
                    "confidence": "medium",
                }
            ]

    parsed_outer_select, parsed_inner_select, parsed_from_suffix = parse_simple_select_wrapper(normalized_original)
    if parsed_outer_select and parsed_inner_select and normalized_sql_eq(parsed_outer_select, parsed_inner_select):
        if re.search(r"\bgroup\s+by\b", parsed_from_suffix or "", flags=re.IGNORECASE):
            if re.search(r"\bhaving\b", parsed_from_suffix or "", flags=re.IGNORECASE):
                if not redundant_having_wrapper_blockers(parsed_from_suffix):
                    return [
                        {
                            "id": f"{sql_key}:llm:recovered_having_wrapper",
                            "source": "llm",
                            "rewrittenSql": normalize_sql(f"SELECT {parsed_inner_select} {parsed_from_suffix}"),
                            "rewriteStrategy": "REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED",
                            "semanticRisk": "low",
                            "confidence": "medium",
                        }
                    ]
            elif not redundant_groupby_wrapper_blockers(parsed_from_suffix):
                return [
                    {
                        "id": f"{sql_key}:llm:recovered_groupby_wrapper",
                        "source": "llm",
                        "rewrittenSql": normalize_sql(f"SELECT {parsed_inner_select} {parsed_from_suffix}"),
                        "rewriteStrategy": "REMOVE_REDUNDANT_GROUP_BY_WRAPPER_RECOVERED",
                        "semanticRisk": "low",
                        "confidence": "medium",
                    }
                ]
        elif not redundant_subquery_blockers(parsed_from_suffix):
            return [
                {
                    "id": f"{sql_key}:llm:recovered_select_wrapper",
                    "source": "llm",
                    "rewrittenSql": normalize_sql(f"SELECT {parsed_inner_select} {parsed_from_suffix}"),
                    "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED",
                    "semanticRisk": "low",
                    "confidence": "medium",
                }
            ]

    cleanup_sql = dynamic_filter_select_cleanup_sql(normalized_original)
    if cleanup_sql:
        return [
            {
                "id": f"{sql_key}:llm:recovered_dynamic_filter_select_cleanup",
                "source": "llm",
                "rewrittenSql": cleanup_sql,
                "rewriteStrategy": "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    cleanup_from_alias_sql = dynamic_filter_from_alias_cleanup_sql(normalized_original)
    if cleanup_from_alias_sql:
        return [
            {
                "id": f"{sql_key}:llm:recovered_dynamic_filter_from_alias_cleanup",
                "source": "llm",
                "rewrittenSql": cleanup_from_alias_sql,
                "rewriteStrategy": "REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    select_match = SELECT_WRAPPER_RE.match(normalized_original)
    if select_match is not None and normalized_sql_eq(select_match.group("outer_select"), select_match.group("inner_select")):
        inner_from = str(select_match.group("inner_from") or "")
        if not redundant_subquery_blockers(inner_from):
            recovered.append(
                {
                    "id": f"{sql_key}:llm:recovered_select_wrapper",
                    "source": "llm",
                    "rewrittenSql": normalize_sql(f"SELECT {select_match.group('inner_select')} {inner_from}"),
                    "rewriteStrategy": "REMOVE_REDUNDANT_SUBQUERY_RECOVERED",
                    "semanticRisk": "low",
                    "confidence": "medium",
                }
            )
    return recovered


def recover_candidates_from_text(sql_key: str, original_sql: str, text: str) -> list[dict[str, Any]]:
    lowered_text = str(text or "").lower()
    if not any(cue in lowered_text for cue in STRUCTURAL_FALLBACK_CUES):
        return []
    if "cte" in lowered_text or "inline" in lowered_text:
        cte = analyze_simple_inline_cte(original_sql)
        if cte.present and cte.collapsible:
            return recover_candidates_from_shape(sql_key, original_sql)
    return recover_candidates_from_shape(sql_key, original_sql)
