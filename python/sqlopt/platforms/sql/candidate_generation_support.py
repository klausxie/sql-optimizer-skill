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
    cleanup_single_table_alias_references,
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
DISTINCT_ON_RE = re.compile(r"\bselect\s+distinct\s+on\s*\((?P<on>[^)]+)\)\s+(?P<select>.+?)\s+from\s+(?P<from>.+?)(?:\s+order\s+by\s+(?P<order>.+))?$", flags=re.IGNORECASE | re.DOTALL)
PAGED_RE = re.compile(r"\border\s+by\b.*\blimit\b", flags=re.IGNORECASE | re.DOTALL)
IN_SINGLE_VALUE_RE = re.compile(
    r"\b(?P<column>[a-z_][a-z0-9_\.]*)\s+IN\s*\(\s*(?P<value>[^,\)]+)\s*\)",
    flags=re.IGNORECASE,
)
NOT_IN_SINGLE_VALUE_RE = re.compile(
    r"\b(?P<column>[a-z_][a-z0-9_\.]*)\s+NOT\s+IN\s*\(\s*(?P<value>[^,\)]+)\s*\)",
    flags=re.IGNORECASE,
)
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
    "redundant outer subquery wrapper",
    "unnecessary subquery wrapper",
    "remove the redundant outer subquery wrapper",
    "remove the unnecessary subquery wrapper",
    "remove unnecessary subquery wrapper",
    "remove redundant subquery",
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
ORDER_BY_CONSTANT_SUFFIX_RE = re.compile(
    r"^(?P<prefix>select\b.+?\bfrom\b.+?)\s+order\s+by\s+(?P<expr>null|\d+|'[^']*'|\"[^\"]*\"|[\d\.]+)\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
BOOLEAN_TAUTOLOGY_SQL_RE = re.compile(
    r"^(?P<prefix>select\b.+?\bfrom\b.+?)\s+where\s+(?P<tautology>1\s*=\s*1|0\s*=\s*0|true)\s*(?:and\s+(?P<rest>.+?))?(?P<suffix>\s+order\s+by\b.+|\s+limit\b.+|\s+offset\b.+|\s+fetch\b.+)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
OR_SAME_COLUMN_SQL_RE = re.compile(
    r"\b(?P<column>[a-z_][a-z0-9_\.]*)\s*=\s*(?P<left>'[^']*'|[^'\s\)]+)\s+OR\s+(?P=column)\s*=\s*(?P<right>'[^']*'|[^'\s\)]+)",
    flags=re.IGNORECASE,
)
CASE_WHEN_TRUE_SQL_RE = re.compile(
    r"\bCASE\s+WHEN\s+TRUE\s+THEN\s+(?P<expr>.+?)\s+ELSE\s+(?P=expr)\s+END\b",
    flags=re.IGNORECASE | re.DOTALL,
)
COALESCE_IDENTITY_SQL_RE = re.compile(
    r"\bCOALESCE\s*\(\s*(?P<expr>[a-z_][a-z0-9_\.]*)\s*,\s*(?P<arg2>(?P=expr)|NULL)\s*\)",
    flags=re.IGNORECASE,
)
ARITH_LITERAL_RE = re.compile(
    r"\b(?P<left>\d+)\s*(?P<op>[+\-*/])\s*(?P<right>\d+)\b",
    flags=re.IGNORECASE,
)
LIMIT_LARGE_SUFFIX_RE = re.compile(
    r"^(?P<prefix>select\b.+?\bfrom\b.+?)\s+limit\s+(?P<value>\d+)\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
NULL_COMPARISON_RE = re.compile(
    r"\b(?P<column>[a-z_][a-z0-9_\.]*)\s*(?P<op>=|!=|<>)\s*null\b",
    flags=re.IGNORECASE,
)
EXISTS_SELF_IDENTITY_SQL_RE = re.compile(
    r"^(?P<prefix>select\b.+?\bfrom\s+(?P<table>[a-z_][a-z0-9_]*)(?:\s+(?P<outer_alias>[a-z_][a-z0-9_]*))?)\s+where\s+exists\s*\(\s*select\s+1\s+from\s+(?P=table)\s+(?P<inner_alias>[a-z_][a-z0-9_]*)\s+where\s+(?P<inner_alias_2>[a-z_][a-z0-9_]*)\.id\s*=\s*(?P<outer_alias_2>[a-z_][a-z0-9_]*)\.id\s*\)\s*(?P<suffix>order\s+by\b.+)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
UNION_WRAPPER_SQL_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(\s*(?P<inner>select\b.+\bunion(?:\s+all)?\b.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)\s*(?P<suffix>(?:order\s+by\b.+|limit\b.+|offset\b.+|fetch\b.+)?)\s*$",
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
    if direct_match is None:
        return None
    cleaned_select, aliases_changed = cleanup_redundant_select_aliases(str(direct_match.group("select") or ""))
    if not aliases_changed:
        return None
    return normalize_sql(f"SELECT {cleaned_select} {direct_match.group('from')}")


def dynamic_filter_from_alias_cleanup_sql(original_sql: str) -> str | None:
    normalized = normalize_sql(original_sql)
    direct_match = SELECT_DIRECT_RE.match(normalized)
    if direct_match is None:
        return None
    select_text = str(direct_match.group("select") or "")
    from_suffix = str(direct_match.group("from") or "")
    cleaned_select_text, cleaned_from_suffix, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        cleaned_from_suffix, changed = cleanup_redundant_from_alias(from_suffix, select_text=select_text)
        cleaned_select_text = select_text
    if not changed:
        return None
    return normalize_sql(f"SELECT {cleaned_select_text} {cleaned_from_suffix}")


def groupby_from_alias_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    direct_match = SELECT_DIRECT_RE.match(normalized_original)
    if direct_match is None:
        return None
    select_text = str(direct_match.group("select") or "")
    from_suffix = str(direct_match.group("from") or "")
    if not re.search(r"\bgroup\s+by\b", from_suffix, flags=re.IGNORECASE):
        return None
    cleaned_select, cleaned_from_suffix, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        return None
    cleaned_select, _ = cleanup_redundant_select_aliases(cleaned_select)
    return normalize_sql(f"SELECT {cleaned_select} {cleaned_from_suffix}")


def distinct_from_alias_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    direct_match = SELECT_DIRECT_RE.match(normalized_original)
    if direct_match is None or not DISTINCT_RE.search(normalized_original):
        return None
    select_text = str(direct_match.group("select") or "")
    from_suffix = str(direct_match.group("from") or "")
    if re.search(r"\bgroup\s+by\b|\bhaving\b|\bunion\b|\bover\s*\(", from_suffix, flags=re.IGNORECASE):
        return None
    cleaned_select, cleaned_from_suffix, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        return None
    return normalize_sql(f"SELECT {cleaned_select} {cleaned_from_suffix}")


def order_by_constant_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = ORDER_BY_CONSTANT_SUFFIX_RE.match(normalized_original)
    if match is None:
        return None
    return normalize_sql(match.group("prefix"))


def boolean_tautology_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = BOOLEAN_TAUTOLOGY_SQL_RE.match(normalized_original)
    if match is None:
        return None
    prefix = normalize_sql(match.group("prefix"))
    rest = normalize_sql(match.group("rest") or "")
    suffix = normalize_sql(match.group("suffix") or "")
    if rest:
        return normalize_sql(f"{prefix} WHERE {rest} {suffix}")
    return normalize_sql(f"{prefix} {suffix}")


def in_list_single_value_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    not_in_match = NOT_IN_SINGLE_VALUE_RE.search(normalized_original)
    if not_in_match is not None:
        column = normalize_sql(not_in_match.group("column"))
        value = normalize_sql(not_in_match.group("value"))
        return normalize_sql(NOT_IN_SINGLE_VALUE_RE.sub(f"{column} != {value}", normalized_original, count=1))
    in_match = IN_SINGLE_VALUE_RE.search(normalized_original)
    if in_match is not None:
        column = normalize_sql(in_match.group("column"))
        value = normalize_sql(in_match.group("value"))
        return normalize_sql(IN_SINGLE_VALUE_RE.sub(f"{column} = {value}", normalized_original, count=1))
    return None


def or_same_column_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = OR_SAME_COLUMN_SQL_RE.search(normalized_original)
    if match is None:
        return None
    column = normalize_sql(match.group("column"))
    left = normalize_sql(match.group("left"))
    right = normalize_sql(match.group("right"))
    replacement = f"{column} IN ({left}, {right})"
    return normalize_sql(OR_SAME_COLUMN_SQL_RE.sub(replacement, normalized_original, count=1))


def case_when_true_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    if CASE_WHEN_TRUE_SQL_RE.search(normalized_original) is None:
        return None
    return normalize_sql(CASE_WHEN_TRUE_SQL_RE.sub(lambda match: normalize_sql(match.group("expr")), normalized_original))


def coalesce_identity_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    if COALESCE_IDENTITY_SQL_RE.search(normalized_original) is None:
        return None
    return normalize_sql(COALESCE_IDENTITY_SQL_RE.sub(lambda match: normalize_sql(match.group("expr")), normalized_original))


def _fold_arithmetic_literals(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        left = int(match.group("left"))
        right = int(match.group("right"))
        op = match.group("op")
        if op == "+":
            value = left + right
        elif op == "-":
            value = left - right
        elif op == "*":
            value = left * right
        elif op == "/":
            if right == 0 or left % right != 0:
                return match.group(0)
            value = left // right
        else:
            return match.group(0)
        return str(value)

    return ARITH_LITERAL_RE.sub(_replace, text)


def expression_folding_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    folded = normalize_sql(_fold_arithmetic_literals(normalized_original))
    if folded == normalized_original:
        return None
    return folded


def limit_large_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = LIMIT_LARGE_SUFFIX_RE.match(normalized_original)
    if match is None:
        return None
    try:
        limit_value = int(match.group("value"))
    except ValueError:
        return None
    if limit_value < 1000000:
        return None
    return normalize_sql(match.group("prefix"))


def null_comparison_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)

    def _replace(match: re.Match[str]) -> str:
        column = normalize_sql(match.group("column"))
        op = str(match.group("op") or "").strip()
        return f"{column} IS NOT NULL" if op in {"!=", "<>"} else f"{column} IS NULL"

    rewritten = NULL_COMPARISON_RE.sub(_replace, normalized_original, count=1)
    if rewritten == normalized_original:
        return None
    return normalize_sql(rewritten)


def distinct_on_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = DISTINCT_ON_RE.match(normalized_original)
    if match is None:
        return None
    distinct_on_expr = normalize_sql(match.group("on"))
    select_list = normalize_sql(match.group("select"))
    from_suffix = normalize_sql(match.group("from"))
    order_by = normalize_sql(match.group("order") or "")
    if select_list != distinct_on_expr:
        return None
    if order_by and not order_by.startswith(distinct_on_expr):
        return None
    suffix = f" ORDER BY {order_by}" if order_by else ""
    return normalize_sql(f"SELECT DISTINCT {select_list} FROM {from_suffix}{suffix}")


def exists_self_cleanup_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = EXISTS_SELF_IDENTITY_SQL_RE.match(normalized_original)
    if match is None:
        return None
    outer_alias = normalize_sql(match.group("outer_alias") or match.group("table") or "")
    outer_alias_2 = normalize_sql(match.group("outer_alias_2") or "")
    inner_alias = normalize_sql(match.group("inner_alias") or "")
    inner_alias_2 = normalize_sql(match.group("inner_alias_2") or "")
    if not outer_alias or outer_alias_2 != outer_alias or inner_alias_2 != inner_alias:
        return None
    suffix = normalize_sql(match.group("suffix") or "")
    return normalize_sql(f"{match.group('prefix')} {suffix}")


def union_wrapper_collapse_sql(original_sql: str) -> str | None:
    normalized_original = normalize_sql(original_sql)
    match = UNION_WRAPPER_SQL_RE.match(normalized_original)
    if match is None:
        return None
    outer_select = normalize_sql(match.group("outer_select"))
    inner_sql = normalize_sql(match.group("inner"))
    suffix = normalize_sql(match.group("suffix") or "")
    first_select = re.match(r"^\s*select\s+(?P<select>.+?)\s+from\b", inner_sql, flags=re.IGNORECASE | re.DOTALL)
    if first_select is None:
        return None
    if normalize_sql(first_select.group("select")) != outer_select:
        return None
    return normalize_sql(f"{inner_sql} {suffix}")


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


def parse_simple_select_wrapper_parts(sql: str) -> tuple[str | None, str | None, str | None, str | None]:
    normalized = normalize_sql(sql)
    prefix_match = OUTER_WRAPPER_PREFIX_RE.match(normalized)
    if prefix_match is None:
        return None, None, None, None
    outer_select = normalize_sql(prefix_match.group("outer_select"))
    open_paren_idx = prefix_match.end() - 1
    close_paren_idx = find_matching_paren(normalized, open_paren_idx)
    if close_paren_idx < 0:
        return None, None, None, None
    inner_sql = normalize_sql(normalized[open_paren_idx + 1 : close_paren_idx])
    inner_match = SELECT_DIRECT_RE.match(inner_sql)
    if inner_match is None:
        return None, None, None, None
    inner_select = normalize_sql(inner_match.group("select"))
    inner_from = normalize_sql(inner_match.group("from"))
    suffix_match = OUTER_ALIAS_SUFFIX_RE.match(normalized[close_paren_idx + 1 :])
    outer_suffix = normalize_sql((suffix_match.group("outer_suffix") if suffix_match else "") or "")
    return outer_select or None, inner_select or None, inner_from or None, outer_suffix or None


def classify_blocked_shape(original_sql: str, sql_unit: dict[str, Any]) -> str:
    normalized = normalize_sql(original_sql)
    dynamic_features = {str(row).upper() for row in (sql_unit.get("dynamicFeatures") or [])}
    statement_type = str(sql_unit.get("statementType") or "").strip().upper()
    if statement_type in {"UPDATE", "DELETE"} and "SET" in dynamic_features:
        return "NO_SAFE_BASELINE_DML_SET"
    if statement_type in {"UPDATE", "DELETE"} and "FOREACH" in dynamic_features:
        return "NO_SAFE_BASELINE_DML_FOREACH"
    if re.search(r"\bunion(?:\s+all)?\b", normalized, flags=re.IGNORECASE):
        return "NO_SAFE_BASELINE_UNION"
    if WINDOW_RE.search(normalized):
        return "NO_SAFE_BASELINE_WINDOW"
    if re.search(r"\bhaving\b", normalized, flags=re.IGNORECASE):
        return "NO_SAFE_BASELINE_HAVING"
    if re.search(r"\bgroup\s+by\b", normalized, flags=re.IGNORECASE):
        return "NO_SAFE_BASELINE_GROUP_BY"
    if DISTINCT_RE.search(normalized):
        return "NO_SAFE_BASELINE_DISTINCT"
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

    distinct_from_alias = distinct_from_alias_cleanup_sql(normalized_original)
    if distinct_from_alias is not None:
        return [
            {
                "id": f"{sql_key}:llm:recovered_distinct_from_alias_cleanup",
                "source": "llm",
                "rewrittenSql": distinct_from_alias,
                "rewriteStrategy": "REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    order_by_constant = order_by_constant_cleanup_sql(normalized_original)
    if order_by_constant is not None:
        return [
            {
                "id": f"{sql_key}:llm:recovered_order_by_constant_cleanup",
                "source": "llm",
                "rewrittenSql": order_by_constant,
                "rewriteStrategy": "REMOVE_CONSTANT_ORDER_BY_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    limit_large = limit_large_cleanup_sql(normalized_original)
    if limit_large is not None and normalize_sql(limit_large) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_large_limit_cleanup",
                "source": "llm",
                "rewrittenSql": limit_large,
                "rewriteStrategy": "REMOVE_LARGE_LIMIT_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    boolean_tautology = boolean_tautology_cleanup_sql(normalized_original)
    if boolean_tautology is not None and normalize_sql(boolean_tautology) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_boolean_tautology_cleanup",
                "source": "llm",
                "rewrittenSql": boolean_tautology,
                "rewriteStrategy": "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    null_comparison = null_comparison_cleanup_sql(normalized_original)
    if null_comparison is not None and normalize_sql(null_comparison) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_null_comparison_cleanup",
                "source": "llm",
                "rewrittenSql": null_comparison,
                "rewriteStrategy": "SIMPLIFY_NULL_COMPARISON_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    in_list_single = in_list_single_value_cleanup_sql(normalized_original)
    if in_list_single is not None and normalize_sql(in_list_single) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_in_list_single_cleanup",
                "source": "llm",
                "rewrittenSql": in_list_single,
                "rewriteStrategy": "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    distinct_on = distinct_on_cleanup_sql(normalized_original)
    if distinct_on is not None and normalize_sql(distinct_on) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_distinct_on_cleanup",
                "source": "llm",
                "rewrittenSql": distinct_on,
                "rewriteStrategy": "SIMPLIFY_DISTINCT_ON_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    or_same_column = or_same_column_cleanup_sql(normalized_original)
    if or_same_column is not None and normalize_sql(or_same_column) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_or_same_column_cleanup",
                "source": "llm",
                "rewrittenSql": or_same_column,
                "rewriteStrategy": "SIMPLIFY_OR_TO_IN_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    exists_self = exists_self_cleanup_sql(normalized_original)
    if exists_self is not None and normalize_sql(exists_self) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_exists_self_cleanup",
                "source": "llm",
                "rewrittenSql": exists_self,
                "rewriteStrategy": "SAFE_EXISTS_REWRITE",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    case_when_true = case_when_true_cleanup_sql(normalized_original)
    if case_when_true is not None and normalize_sql(case_when_true) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_case_when_true_cleanup",
                "source": "llm",
                "rewrittenSql": case_when_true,
                "rewriteStrategy": "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    coalesce_identity = coalesce_identity_cleanup_sql(normalized_original)
    if coalesce_identity is not None and normalize_sql(coalesce_identity) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_coalesce_identity_cleanup",
                "source": "llm",
                "rewrittenSql": coalesce_identity,
                "rewriteStrategy": "SIMPLIFY_COALESCE_IDENTITY_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    union_wrapper = union_wrapper_collapse_sql(normalized_original)
    if union_wrapper is not None and normalize_sql(union_wrapper) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_union_wrapper_collapse",
                "source": "llm",
                "rewrittenSql": union_wrapper,
                "rewriteStrategy": "SAFE_UNION_COLLAPSE",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    expression_folding = expression_folding_cleanup_sql(normalized_original)
    if expression_folding is not None and normalize_sql(expression_folding) != normalized_original:
        return [
            {
                "id": f"{sql_key}:llm:recovered_expression_folding_cleanup",
                "source": "llm",
                "rewrittenSql": expression_folding,
                "rewriteStrategy": "FOLD_CONSTANT_EXPRESSION_RECOVERED",
                "semanticRisk": "low",
                "confidence": "medium",
            }
        ]

    parsed_outer_select, parsed_inner_select, parsed_inner_from, parsed_outer_suffix = parse_simple_select_wrapper_parts(
        normalized_original
    )
    parsed_from_suffix = normalize_sql(f"{parsed_inner_from or ''} {parsed_outer_suffix or ''}").strip() or parsed_inner_from
    if parsed_outer_select and parsed_inner_select and normalized_sql_eq(parsed_outer_select, parsed_inner_select):
        inner_from_for_blockers = parsed_inner_from or parsed_from_suffix or ""
        if re.search(r"\bgroup\s+by\b", parsed_from_suffix or "", flags=re.IGNORECASE):
            if re.search(r"\bhaving\b", parsed_from_suffix or "", flags=re.IGNORECASE):
                if not redundant_having_wrapper_blockers(inner_from_for_blockers):
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
            elif not redundant_groupby_wrapper_blockers(inner_from_for_blockers):
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
        elif not redundant_subquery_blockers(inner_from_for_blockers):
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

    groupby_alias_cleanup = groupby_from_alias_cleanup_sql(normalized_original)
    if groupby_alias_cleanup:
        rewrite_strategy = "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED"
        if re.search(r"\bhaving\b", normalized_original, flags=re.IGNORECASE):
            rewrite_strategy = "REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED"
        return [
            {
                "id": f"{sql_key}:llm:recovered_groupby_from_alias_cleanup",
                "source": "llm",
                "rewrittenSql": groupby_alias_cleanup,
                "rewriteStrategy": rewrite_strategy,
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
