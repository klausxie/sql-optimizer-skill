from __future__ import annotations

import re
from typing import Any

from .canonicalization_support import (
    SELECT_DIRECT_RE,
    cleanup_redundant_select_aliases,
    cleanup_single_table_alias_references,
    split_select_list,
    strip_redundant_projection_alias,
    strip_sql_comments,
)
from .aggregation_analysis import analyze_aggregation_query
from .cte_analysis import analyze_simple_inline_cte
from .dynamic_template_support import parse_select_wrapper_template, render_flattened_select_template

_WS_RE = re.compile(r"\s+")
_COUNT_SUBQUERY_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_SELECT_FROM_RE = re.compile(r"^\s*select\s+.+?\s+(?P<from_suffix>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)
_COUNT_DIRECT_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_UPDATE_RE = re.compile(
    r"^\s*update\s+(?P<table>[a-z_][a-z0-9_\.]*)\s+set\s+(?P<set_clause>.+?)(?:\s+where\s+(?P<where_clause>.+))?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_COUNT_WRAPPER_BLOCKERS = (
    r"\bdistinct\b",
    r"\bgroup\s+by\b",
    r"\bhaving\b",
    r"\bunion\b",
    r"\bover\s*\(",
    r"\blimit\b",
    r"\boffset\b",
    r"\bfetch\b",
)
_BOOLEAN_TAUTOLOGY_RE = re.compile(r"^(1\s*=\s*1|0\s*=\s*0|true)$", flags=re.IGNORECASE)
_IN_SINGLE_VALUE_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s+in\s*\(\s*(?P<value>[^,\)]+)\s*\)$",
    flags=re.IGNORECASE,
)
_NOT_IN_SINGLE_VALUE_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s+not\s+in\s*\(\s*(?P<value>[^,\)]+)\s*\)$",
    flags=re.IGNORECASE,
)
_EQ_VALUE_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s*=\s*(?P<value>.+)$",
    flags=re.IGNORECASE,
)
_NEQ_VALUE_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s*(?:<>|!=)\s*(?P<value>.+)$",
    flags=re.IGNORECASE,
)
_ORDER_BY_CONSTANT_ONLY_RE = re.compile(
    r"^(\d+|null|'[^']*'|\"[^\"]*\"|[\d\.]+)(\s*,\s*(\d+|null|'[^']*'|\"[^\"]*\"|[\d\.]+))*$",
    flags=re.IGNORECASE,
)
_OR_SAME_COLUMN_PREDICATE_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s*=\s*(?P<left>'[^']*'|[^'\s\)]+)\s+or\s+(?P=column)\s*=\s*(?P<right>'[^']*'|[^'\s\)]+)$",
    flags=re.IGNORECASE,
)
_CASE_WHEN_TRUE_RE = re.compile(
    r"\bcase\s+when\s+true\s+then\s+(?P<expr>.+?)\s+else\s+(?P=expr)\s+end\b",
    flags=re.IGNORECASE | re.DOTALL,
)
_COALESCE_IDENTITY_RE = re.compile(
    r"\bcoalesce\s*\(\s*(?P<expr>[a-z_][a-z0-9_\.]*)\s*,\s*(?P<arg2>(?P=expr)|null)\s*\)",
    flags=re.IGNORECASE,
)
_ARITH_LITERAL_RE = re.compile(
    r"\b(?P<left>\d+)\s*(?P<op>[+\-*/])\s*(?P<right>\d+)\b",
    flags=re.IGNORECASE,
)
_LIMIT_LARGE_ONLY_RE = re.compile(r"^limit\s+(?P<value>\d+)$", flags=re.IGNORECASE)
_NULL_COMPARISON_ONLY_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s*(?P<op>=|!=|<>)\s*null$",
    flags=re.IGNORECASE,
)
_NULL_IS_COMPARISON_RE = re.compile(
    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s+is\s+(?P<neg>not\s+)?null$",
    flags=re.IGNORECASE,
)
_DISTINCT_ON_EQUIVALENT_RE = re.compile(
    r"^distinct\s+on\s*\((?P<on>[^)]+)\)\s+(?P<select>.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_DISTINCT_EQUIVALENT_RE = re.compile(
    r"^distinct\s+(?P<select>.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_EXISTS_SELF_RE = re.compile(
    r"^exists\s*\(\s*select\s+1\s+from\s+(?P<table>[a-z_][a-z0-9_]*)\s+(?P<inner_alias>[a-z_][a-z0-9_]*)\s+where\s+(?P<inner_alias_2>[a-z_][a-z0-9_]*)\.id\s*=\s*(?P<outer_alias>[a-z_][a-z0-9_]*)\.id\s*\)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_EXISTS_TO_IN_BEFORE_RE = re.compile(
    r"^exists\s*\(\s*select\s+1\s+from\s+(?P<table>[a-z_][a-z0-9_]*)\s+(?P<inner_alias>[a-z_][a-z0-9_]*)\s+where\s+(?P<inner_alias_2>[a-z_][a-z0-9_]*)\.(?P<inner_column>[a-z_][a-z0-9_]*)\s*=\s*(?P<outer_alias>[a-z_][a-z0-9_]*)\.(?P<outer_column>[a-z_][a-z0-9_]*)\s*\)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_EXISTS_TO_IN_AFTER_RE = re.compile(
    r"^(?P<outer_expr>[a-z_][a-z0-9_\.]*)\s+in\s*\(\s*select\s+(?:distinct\s+)?(?P<inner_expr>[a-z_][a-z0-9_\.]*)\s+from\s+(?P<table>[a-z_][a-z0-9_]*)\s+(?P<inner_alias>[a-z_][a-z0-9_]*)\s*\)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_JOIN_KEYWORD_RE = re.compile(r"\b(?:left|right|full|inner|cross|semi|anti)?\s*join\b", flags=re.IGNORECASE)
_UNION_WRAPPER_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(\s*(?P<inner>select\b.+\bunion(?:\s+all)?\b.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)\s*(?P<suffix>(?:order\s+by\b.+|limit\b.+|offset\b.+|fetch\b.+)?)\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _normalize_sql(text: str) -> str:
    return _WS_RE.sub(" ", strip_sql_comments(str(text or "")).strip()).lower()


def _extract_select_list(sql: str) -> str | None:
    match = re.search(r"^\s*select\s+(.*?)\s+from\s", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _normalize_sql(match.group(1))


def _projection_signature(select_list: str | None) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    cleaned_select_list, _ = cleanup_redundant_select_aliases(select_list)
    parts = split_select_list(cleaned_select_list)
    return tuple(_normalize_sql(strip_redundant_projection_alias(part)) for part in parts)


def _extract_select_from_suffix(sql: str) -> str | None:
    match = _SELECT_FROM_RE.search(str(sql or "").strip())
    if not match:
        return None
    return _normalize_sql(match.group("from_suffix"))


def _inline_simple_count_wrapper(sql: str) -> str | None:
    normalized = str(sql or "").strip()
    match = _COUNT_SUBQUERY_RE.match(normalized)
    if not match:
        return None
    inner_sql = str(match.group("inner") or "").strip()
    if not inner_sql:
        return None
    inner_normalized = _normalize_sql(inner_sql)
    if any(re.search(pattern, inner_normalized, flags=re.IGNORECASE) for pattern in _COUNT_WRAPPER_BLOCKERS):
        return None
    from_suffix = _extract_select_from_suffix(inner_sql)
    count_match = _COUNT_DIRECT_RE.match(normalized)
    count_expr = _normalize_sql((count_match.group("count_expr") if count_match else "") or "")
    if not from_suffix or count_expr not in {"1", "*"}:
        return None
    return f"select count(*) {from_suffix}"


def _inline_simple_select_wrapper(sql: str) -> str | None:
    outer_select, inner_select, flattened_from = parse_select_wrapper_template(sql)
    if outer_select is None or inner_select is None or flattened_from is None:
        return None
    if _normalize_sql(outer_select) == "*":
        return render_flattened_select_template(inner_select, flattened_from)
    if _normalize_sql(outer_select) != _normalize_sql(inner_select):
        return None
    return render_flattened_select_template(inner_select, flattened_from)


def _inline_union_wrapper(sql: str) -> str | None:
    normalized = strip_sql_comments(str(sql or "")).strip()
    match = _UNION_WRAPPER_RE.match(normalized)
    if not match:
        return None
    inner_sql = str(match.group("inner") or "").strip()
    outer_select = _normalize_sql(match.group("outer_select") or "")
    first_select = re.match(r"^\s*select\s+(?P<select>.+?)\s+from\b", inner_sql, flags=re.IGNORECASE | re.DOTALL)
    if first_select is None:
        return None
    if _normalize_sql(first_select.group("select") or "") != outer_select:
        return None
    suffix = str(match.group("suffix") or "").strip()
    return f"{inner_sql} {suffix}".strip()


def _normalize_groupby_from_alias_cleanup(sql: str) -> str | None:
    direct_match = SELECT_DIRECT_RE.match(str(sql or "").strip())
    if direct_match is None:
        return None
    select_text = str(direct_match.group("select") or "").strip()
    from_suffix = str(direct_match.group("from") or "").strip()
    if not re.search(r"\bgroup\s+by\b", from_suffix, flags=re.IGNORECASE):
        return None
    cleaned_select, cleaned_from, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        return None
    cleaned_select, _ = cleanup_redundant_select_aliases(cleaned_select)
    return f"SELECT {cleaned_select} {cleaned_from}"


def _normalize_distinct_from_alias_cleanup(sql: str) -> str | None:
    direct_match = SELECT_DIRECT_RE.match(str(sql or "").strip())
    if direct_match is None:
        return None
    select_text = str(direct_match.group("select") or "").strip()
    from_suffix = str(direct_match.group("from") or "").strip()
    if not select_text.lower().startswith("distinct "):
        return None
    if re.search(r"\bgroup\s+by\b|\bhaving\b|\bunion\b|\bover\s*\(", from_suffix, flags=re.IGNORECASE):
        return None
    cleaned_select, cleaned_from, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        return None
    return f"SELECT {cleaned_select} {cleaned_from}"


def _semantic_subject_sql(sql: str) -> str:
    normalized = strip_sql_comments(str(sql or "")).strip()
    collapsed_count = _inline_simple_count_wrapper(normalized)
    if collapsed_count:
        return collapsed_count
    collapsed_union_wrapper = _inline_union_wrapper(normalized)
    if collapsed_union_wrapper:
        return collapsed_union_wrapper
    distinct_alias_cleanup = _normalize_distinct_from_alias_cleanup(normalized)
    if distinct_alias_cleanup:
        return distinct_alias_cleanup
    groupby_alias_cleanup = _normalize_groupby_from_alias_cleanup(normalized)
    if groupby_alias_cleanup:
        return groupby_alias_cleanup
    collapsed_wrapper = _inline_simple_select_wrapper(normalized)
    if collapsed_wrapper:
        return collapsed_wrapper
    cte_analysis = analyze_simple_inline_cte(normalized)
    if cte_analysis.collapsible and cte_analysis.inlined_sql:
        return cte_analysis.inlined_sql
    return normalized


def _normalize_projection_alias(expr: str) -> str:
    value = str(expr or "").strip().lower()
    # Remove trailing alias styles: "count(*) as c" / "count(*) c"
    value = re.sub(r"\s+as\s+[a-z_][a-z0-9_]*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+[a-z_][a-z0-9_]*$", "", value, flags=re.IGNORECASE)
    return _normalize_sql(value)


def _strip_identifier_qualifiers(expr: str) -> str:
    return re.sub(r"\b[a-z_][a-z0-9_]*\.", "", str(expr or ""), flags=re.IGNORECASE)


def _is_count_star_one_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    normalized_before = _normalize_projection_alias(before)
    normalized_after = _normalize_projection_alias(after)
    pair = {normalized_before, normalized_after}
    return pair == {"count(1)", "count(*)"}


def _is_projection_alias_only_equivalent(before: str | None, after: str | None) -> bool:
    before_signature = _projection_signature(before)
    after_signature = _projection_signature(after)
    return before_signature is not None and before_signature == after_signature


def _projection_signature_without_qualifiers(select_list: str | None) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    cleaned_select_list, _ = cleanup_redundant_select_aliases(select_list)
    parts = split_select_list(cleaned_select_list)
    return tuple(_normalize_sql(_strip_identifier_qualifiers(strip_redundant_projection_alias(part))) for part in parts)


def _is_projection_qualifier_only_equivalent(before: str | None, after: str | None) -> bool:
    before_signature = _projection_signature_without_qualifiers(before)
    after_signature = _projection_signature_without_qualifiers(after)
    return before_signature is not None and before_signature == after_signature


def _is_clause_qualifier_only_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    return _normalize_sql(_strip_identifier_qualifiers(before)) == _normalize_sql(_strip_identifier_qualifiers(after))


def _extract_where_clause(sql: str) -> str | None:
    match = re.search(
        r"\bwhere\b(.*?)(\border\s+by\b|\blimit\b|\boffset\b|\bfetch\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    where_text = _normalize_sql(match.group(1))
    return where_text or None


def _split_top_level_and_conjuncts(where_clause: str | None) -> tuple[str, ...] | None:
    text = str(where_clause or "").strip()
    if not text:
        return None
    normalized_text = _normalize_sql(text)
    if re.search(r"\b(?:exists|select|join)\b", normalized_text, flags=re.IGNORECASE):
        return None

    segments: list[str] = []
    current: list[str] = []
    depth = 0
    in_single_quote = False
    in_double_quote = False
    between_pending = False
    i = 0

    def _read_word(start: int) -> tuple[str, int]:
        end = start
        while end < len(text) and (text[end].isalnum() or text[end] in {"_", "."}):
            end += 1
        return text[start:end], end

    while i < len(text):
        ch = text[i]
        if in_single_quote:
            current.append(ch)
            if ch == "'" and i + 1 < len(text) and text[i + 1] == "'":
                current.append(text[i + 1])
                i += 2
                continue
            if ch == "'":
                in_single_quote = False
            i += 1
            continue
        if in_double_quote:
            current.append(ch)
            if ch == '"' and i + 1 < len(text) and text[i + 1] == '"':
                current.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_double_quote = False
            i += 1
            continue
        if ch == "'":
            in_single_quote = True
            current.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double_quote = True
            current.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            current.append(ch)
            i += 1
            continue
        if ch == ")":
            if depth == 0:
                return None
            depth -= 1
            current.append(ch)
            i += 1
            continue
        if depth == 0 and ch.isalpha():
            word, end = _read_word(i)
            lower = word.lower()
            if lower == "and":
                if between_pending:
                    current.append(word)
                    between_pending = False
                else:
                    segment = _normalize_sql("".join(current).strip())
                    if not segment:
                        return None
                    segments.append(segment)
                    current = []
                i = end
                continue
            if lower == "or":
                return None
            if lower == "between":
                between_pending = True
            current.append(word)
            i = end
            continue
        current.append(ch)
        i += 1

    if between_pending:
        return None

    final_segment = _normalize_sql("".join(current).strip())
    if not final_segment:
        return None
    segments.append(final_segment)
    if len(segments) < 2:
        return None
    return tuple(sorted(segments))


def _is_boolean_tautology_only_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is not None:
        return False
    return _BOOLEAN_TAUTOLOGY_RE.match(str(before).strip()) is not None


def _is_single_value_in_list_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    before_text = _normalize_sql(before)
    after_text = _normalize_sql(after)
    in_match = _IN_SINGLE_VALUE_RE.match(before_text)
    eq_match = _EQ_VALUE_RE.match(after_text)
    if in_match is not None and eq_match is not None:
        return (
            _normalize_sql(in_match.group("column")) == _normalize_sql(eq_match.group("column"))
            and _normalize_sql(in_match.group("value")) == _normalize_sql(eq_match.group("value"))
        )
    not_in_match = _NOT_IN_SINGLE_VALUE_RE.match(before_text)
    neq_match = _NEQ_VALUE_RE.match(after_text)
    if not_in_match is not None and neq_match is not None:
        return (
            _normalize_sql(not_in_match.group("column")) == _normalize_sql(neq_match.group("column"))
            and _normalize_sql(not_in_match.group("value")) == _normalize_sql(neq_match.group("value"))
        )
    return False


def _is_constant_order_by_removed_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is not None:
        return False
    return _ORDER_BY_CONSTANT_ONLY_RE.match(str(before).strip()) is not None


def _is_same_column_or_to_in_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    before_match = _OR_SAME_COLUMN_PREDICATE_RE.match(_normalize_sql(before))
    in_pattern = re.match(
        r"^(?P<column>[a-z_][a-z0-9_\.]*)\s+in\s*\(\s*(?P<left>'[^']*'|[^,\)]+)\s*,\s*(?P<right>'[^']*'|[^,\)]+)\s*\)$",
        _normalize_sql(after),
        flags=re.IGNORECASE,
    )
    if before_match is None or in_pattern is None:
        return False
    return (
        _normalize_sql(before_match.group("column")) == _normalize_sql(in_pattern.group("column"))
        and {
            _normalize_sql(before_match.group("left")),
            _normalize_sql(before_match.group("right")),
        }
        == {
            _normalize_sql(in_pattern.group("left")),
            _normalize_sql(in_pattern.group("right")),
        }
    )


def _normalized_projection_signature_with_transform(
    select_list: str | None,
    transform: callable[[str], str],
) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    transformed = transform(select_list)
    cleaned_select_list, _ = cleanup_redundant_select_aliases(transformed)
    parts = split_select_list(cleaned_select_list)
    return tuple(_normalize_sql(strip_redundant_projection_alias(part)) for part in parts)


def _normalize_case_when_true_projection(select_list: str | None) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    return _normalized_projection_signature_with_transform(
        select_list,
        lambda text: _CASE_WHEN_TRUE_RE.sub(lambda match: _normalize_sql(match.group("expr")), text),
    )


def _normalize_coalesce_identity_projection(select_list: str | None) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    return _normalized_projection_signature_with_transform(
        select_list,
        lambda text: _COALESCE_IDENTITY_RE.sub(lambda match: _normalize_sql(match.group("expr")), text),
    )


def _fold_constant_arithmetic(text: str | None) -> str | None:
    if text is None:
        return None

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

    return _normalize_sql(_ARITH_LITERAL_RE.sub(_replace, text))


def _is_case_when_true_projection_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    return _normalize_case_when_true_projection(before) == _projection_signature(after)


def _is_coalesce_identity_projection_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    return _normalize_coalesce_identity_projection(before) == _projection_signature(after)


def _is_constant_expression_folding_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    return _fold_constant_arithmetic(before) == _normalize_sql(after)


def _is_large_limit_removed_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is not None:
        return False
    match = _LIMIT_LARGE_ONLY_RE.match(_normalize_sql(before))
    if match is None:
        return False
    try:
        return int(match.group("value")) >= 1000000
    except ValueError:
        return False


def _is_null_comparison_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    before_match = _NULL_COMPARISON_ONLY_RE.match(_normalize_sql(before))
    after_match = _NULL_IS_COMPARISON_RE.match(_normalize_sql(after))
    if before_match is None or after_match is None:
        return False
    if _normalize_sql(before_match.group("column")) != _normalize_sql(after_match.group("column")):
        return False
    before_op = str(before_match.group("op") or "").strip()
    after_is_not = bool(str(after_match.group("neg") or "").strip())
    return (before_op == "=" and not after_is_not) or (before_op in {"!=", "<>"} and after_is_not)


def _is_distinct_on_equivalent(before: str | None, after: str | None, ordering_before: str | None, ordering_after: str | None) -> bool:
    if before is None or after is None:
        return False
    before_match = _DISTINCT_ON_EQUIVALENT_RE.match(_normalize_sql(before))
    after_match = _DISTINCT_EQUIVALENT_RE.match(_normalize_sql(after))
    if before_match is None or after_match is None:
        return False
    distinct_on_expr = _normalize_sql(before_match.group("on"))
    before_select = _normalize_sql(before_match.group("select"))
    after_select = _normalize_sql(after_match.group("select"))
    if before_select != distinct_on_expr or after_select != distinct_on_expr:
        return False
    if ordering_before is None:
        return False
    normalized_ordering_before = _normalize_sql(ordering_before)
    normalized_ordering_after = _normalize_sql(ordering_after or "")
    if not normalized_ordering_before.startswith(distinct_on_expr):
        return False
    return normalized_ordering_after == normalized_ordering_before


def _is_exists_self_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is not None:
        return False
    return _EXISTS_SELF_RE.match(_normalize_sql(before)) is not None


def _is_exists_to_in_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    if _JOIN_KEYWORD_RE.search(_normalize_sql(before)) or _JOIN_KEYWORD_RE.search(_normalize_sql(after)):
        return False
    before_match = _EXISTS_TO_IN_BEFORE_RE.match(_normalize_sql(before))
    after_match = _EXISTS_TO_IN_AFTER_RE.match(_normalize_sql(after))
    if before_match is None or after_match is None:
        return False
    if _normalize_sql(before_match.group("table")) != _normalize_sql(after_match.group("table")):
        return False
    if _normalize_sql(before_match.group("inner_alias")) != _normalize_sql(before_match.group("inner_alias_2")):
        return False

    outer_alias = _normalize_sql(before_match.group("outer_alias"))
    outer_column = _normalize_sql(before_match.group("outer_column"))
    inner_alias = _normalize_sql(before_match.group("inner_alias"))
    inner_column = _normalize_sql(before_match.group("inner_column"))
    outer_expr = _normalize_sql(after_match.group("outer_expr"))
    inner_expr = _normalize_sql(after_match.group("inner_expr"))

    valid_outer_exprs = {outer_column, f"{outer_alias}.{outer_column}"}
    valid_inner_exprs = {inner_column, f"{inner_alias}.{inner_column}"}
    return outer_expr in valid_outer_exprs and inner_expr in valid_inner_exprs


def _is_top_level_and_order_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    before_segments = _split_top_level_and_conjuncts(before)
    after_segments = _split_top_level_and_conjuncts(after)
    return before_segments is not None and before_segments == after_segments


def _extract_order_by_clause(sql: str) -> str | None:
    match = re.search(
        r"\border\s+by\b(.*?)(\blimit\b|\boffset\b|\bfetch\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    order_text = _normalize_sql(match.group(1))
    return order_text or None


def _extract_pagination_clause(sql: str) -> str | None:
    clauses: list[str] = []
    limit_match = re.search(r"\blimit\b\s+([0-9?#{}:_\-]+)", sql, flags=re.IGNORECASE)
    if limit_match:
        clauses.append(f"limit {limit_match.group(1).lower()}")
    offset_match = re.search(r"\boffset\b\s+([0-9?#{}:_\-]+)", sql, flags=re.IGNORECASE)
    if offset_match:
        clauses.append(f"offset {offset_match.group(1).lower()}")
    fetch_match = re.search(
        r"\bfetch\s+first\s+([0-9?#{}:_\-]+)\s+rows?\s+only\b",
        sql,
        flags=re.IGNORECASE,
    )
    if fetch_match:
        clauses.append(f"fetch first {fetch_match.group(1).lower()} rows only")
    if not clauses:
        return None
    return " ".join(clauses)


def _extract_update_parts(sql: str) -> tuple[str | None, str | None, str | None]:
    match = _UPDATE_RE.match(str(sql or "").strip())
    if not match:
        return None, None, None
    table = _normalize_sql(match.group("table") or "")
    set_clause = _normalize_sql(match.group("set_clause") or "")
    where_clause = _normalize_sql(match.group("where_clause") or "") or None
    return table or None, set_clause or None, where_clause


def _is_update_statement(sql: str) -> bool:
    return _UPDATE_RE.match(str(sql or "").strip()) is not None


def _build_dml_checks(original_sql: str, rewritten_sql: str) -> dict[str, Any] | None:
    before_table, before_set, before_where = _extract_update_parts(original_sql)
    after_table, after_set, after_where = _extract_update_parts(rewritten_sql)
    if before_table is None or after_table is None:
        return None

    if before_table == after_table:
        projection_check = _build_check(
            status="PASS",
            reason_code="SEMANTIC_DML_TARGET_STABLE",
            detail="update target table unchanged",
            before=before_table,
            after=after_table,
        )
    else:
        projection_check = _build_check(
            status="FAIL",
            reason_code="SEMANTIC_DML_TARGET_CHANGED",
            detail="update target table changed",
            before=before_table,
            after=after_table,
        )

    if before_set is None or after_set is None:
        set_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_DML_SET_PARSE_INCOMPLETE",
            detail="failed to parse update set clause from one or both sqls",
            before=before_set,
            after=after_set,
        )
    elif before_set == after_set:
        set_check = _build_check(
            status="PASS",
            reason_code="SEMANTIC_DML_SET_STABLE",
            detail="update set clause unchanged",
            before=before_set,
            after=after_set,
        )
    else:
        set_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_DML_SET_CHANGED",
            detail="update set clause changed and requires manual review",
            before=before_set,
            after=after_set,
        )

    predicate_check = _compare_text_clause(
        before=before_where,
        after=after_where,
        same_reason_code="SEMANTIC_PREDICATE_STABLE",
        change_reason_code="SEMANTIC_PREDICATE_CHANGED",
        missing_reason_code="SEMANTIC_PREDICATE_ADDED_OR_REMOVED",
        missing_detail="where clause added or removed",
    )
    return {
        "predicate": predicate_check,
        "projection": projection_check,
        "ordering": _build_check(status="PASS", reason_code="SEMANTIC_ORDERING_STABLE", detail="clause absent in both sqls"),
        "pagination": _build_check(status="PASS", reason_code="SEMANTIC_PAGINATION_STABLE", detail="clause absent in both sqls"),
        "dmlSet": set_check,
    }


def _is_safe_aggregation_wrapper_equivalent(original_sql: str, rewritten_sql: str) -> str | None:
    analysis = analyze_aggregation_query(original_sql, rewritten_sql)
    family = str((analysis.capability_profile or {}).get("safeBaselineFamily") or "").strip().upper()
    if family == "REDUNDANT_GROUP_BY_WRAPPER":
        return "SEMANTIC_SAFE_BASELINE_REDUNDANT_GROUP_BY_WRAPPER"
    if family == "REDUNDANT_HAVING_WRAPPER":
        return "SEMANTIC_SAFE_BASELINE_REDUNDANT_HAVING_WRAPPER"
    if family == "DISTINCT_FROM_ALIAS_CLEANUP":
        return "SEMANTIC_SAFE_BASELINE_DISTINCT_FROM_ALIAS_CLEANUP"
    if family == "GROUP_BY_FROM_ALIAS_CLEANUP":
        return "SEMANTIC_SAFE_BASELINE_GROUP_BY_FROM_ALIAS_CLEANUP"
    if family == "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP":
        return "SEMANTIC_SAFE_BASELINE_GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"
    return None


def _build_check(
    *,
    status: str,
    reason_code: str | None = None,
    detail: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
    }
    if reason_code:
        payload["reasonCode"] = reason_code
    if detail:
        payload["detail"] = detail
    if before is not None or after is not None:
        payload["evidence"] = {"before": before, "after": after}
    return payload


def _infer_fingerprint_status(equivalence: dict[str, Any]) -> str:
    key_status = str(((equivalence.get("keySetHash") or {}).get("status") or "")).strip().upper()
    sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    if key_status == "MISMATCH":
        return "MISMATCH"
    if key_status == "MATCH":
        return "MATCH"
    if sample_status == "MISMATCH":
        return "MISMATCH_SAMPLE"
    if sample_status == "MATCH":
        return "SAMPLE_MATCH"
    if "ERROR" in {key_status, sample_status}:
        return "ERROR"
    if key_status:
        return key_status
    if sample_status:
        return sample_status
    return "SKIPPED"


def _confidence_rank(confidence: str) -> int:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return order.get(str(confidence or "").upper(), 0)


def _confidence_from_status_and_evidence_level(*, status: str, evidence_level: str) -> str:
    if status == "PASS":
        if evidence_level == "DB_COUNT":
            return "MEDIUM"
        return "LOW"
    if status == "FAIL":
        return "HIGH" if evidence_level == "DB_COUNT" else "MEDIUM"
    return "MEDIUM" if evidence_level == "DB_COUNT" else "LOW"


def _extract_fingerprint_strength(equivalence: dict[str, Any], fingerprint_status: str) -> str:
    strengths: list[str] = []
    for row in equivalence.get("evidenceRefObjects") or []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip().upper()
        if source != "DB_FINGERPRINT":
            continue
        strength = str(row.get("match_strength") or "").strip().upper()
        if strength:
            strengths.append(strength)
    if "EXACT" in strengths:
        return "EXACT"
    if "PARTIAL" in strengths:
        return "PARTIAL"
    if fingerprint_status == "MATCH":
        return "EXACT"
    if fingerprint_status == "SAMPLE_MATCH":
        return "PARTIAL"
    return "NONE"


def _has_order_sensitive_exact_evidence(equivalence: dict[str, Any]) -> bool:
    sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    if sample_status == "MATCH":
        return True
    for row in equivalence.get("evidenceRefObjects") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "").strip().upper() != "DB_FINGERPRINT":
            continue
        fingerprint_key = str(row.get("fingerprint_key") or "").strip().lower()
        match_strength = str(row.get("match_strength") or "").strip().upper()
        if fingerprint_key == "row_sample_hash" and match_strength == "EXACT":
            return True
    return False


def _compare_text_clause(
    *,
    before: str | None,
    after: str | None,
    same_reason_code: str,
    change_reason_code: str,
    missing_reason_code: str,
    missing_detail: str,
    missing_status: str = "FAIL",
    changed_status: str = "UNCERTAIN",
) -> dict[str, Any]:
    if before is None and after is None:
        return _build_check(status="PASS", reason_code=same_reason_code, detail="clause absent in both sqls")
    if before is None or after is None:
        return _build_check(
            status=missing_status,
            reason_code=missing_reason_code,
            detail=missing_detail,
            before=before,
            after=after,
        )
    if before == after:
        return _build_check(status="PASS", reason_code=same_reason_code, detail="clause text matches", before=before, after=after)
    return _build_check(
        status=changed_status,
        reason_code=change_reason_code,
        detail="clause changed and requires manual review",
        before=before,
        after=after,
    )


def build_semantic_equivalence(
    *,
    original_sql: str,
    rewritten_sql: str,
    equivalence: dict[str, Any],
) -> dict[str, Any]:
    original_subject_sql = _semantic_subject_sql(original_sql)
    rewritten_subject_sql = _semantic_subject_sql(rewritten_sql)
    row_count = dict(equivalence.get("rowCount") or {})
    row_count_status = str(row_count.get("status") or "").upper()
    fingerprint_status = _infer_fingerprint_status(equivalence)
    key_set_status = str(((equivalence.get("keySetHash") or {}).get("status") or "")).strip().upper()
    row_sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    fingerprint_strength = _extract_fingerprint_strength(equivalence, fingerprint_status)
    order_sensitive_exact_evidence = _has_order_sensitive_exact_evidence(equivalence)
    checked = equivalence.get("checked")
    is_dml_comparison = _is_update_statement(original_subject_sql) and _is_update_statement(rewritten_subject_sql)
    predicate_before: str | None = None
    predicate_after: str | None = None
    predicate_check: dict[str, Any] = {"status": "PASS", "reasonCode": None}
    ordering_before: str | None = None
    ordering_after: str | None = None
    ordering_check: dict[str, Any] = {"status": "PASS", "reasonCode": None}
    pagination_before: str | None = None
    pagination_after: str | None = None

    projection_before = _extract_select_list(original_subject_sql)
    projection_after = _extract_select_list(rewritten_subject_sql)
    count_projection_equivalent = _is_count_star_one_equivalent(projection_before, projection_after)
    alias_only_projection_equivalent = _is_projection_alias_only_equivalent(projection_before, projection_after)
    qualifier_only_projection_equivalent = _is_projection_qualifier_only_equivalent(projection_before, projection_after)
    if is_dml_comparison:
        checks = _build_dml_checks(original_subject_sql, rewritten_subject_sql) or {}
        projection_check = dict(checks.get("projection") or {})
    else:
        if projection_before is None or projection_after is None:
            projection_check = _build_check(
                status="UNCERTAIN",
                reason_code="SEMANTIC_PROJECTION_PARSE_INCOMPLETE",
                detail="failed to parse select list from one or both sqls",
                before=projection_before,
                after=projection_after,
            )
        elif projection_before == projection_after:
            projection_check = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PROJECTION_STABLE",
                detail="projection list unchanged",
                before=projection_before,
                after=projection_after,
            )
        elif alias_only_projection_equivalent:
            projection_check = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PROJECTION_ALIAS_ONLY_EQUIVALENT",
                detail="projection change only removes redundant aliases",
                before=projection_before,
                after=projection_after,
            )
        else:
            projection_check = _build_check(
                status="UNCERTAIN",
                reason_code="SEMANTIC_PROJECTION_CHANGED",
                detail="projection list changed and may affect result shape",
                before=projection_before,
                after=projection_after,
            )

        predicate_before = _extract_where_clause(original_subject_sql)
        predicate_after = _extract_where_clause(rewritten_subject_sql)
        predicate_check = _compare_text_clause(
            before=predicate_before,
            after=predicate_after,
            same_reason_code="SEMANTIC_PREDICATE_STABLE",
            change_reason_code="SEMANTIC_PREDICATE_CHANGED",
            missing_reason_code="SEMANTIC_PREDICATE_ADDED_OR_REMOVED",
            missing_detail="where clause added or removed",
        )
        ordering_before = _extract_order_by_clause(original_subject_sql)
        ordering_after = _extract_order_by_clause(rewritten_subject_sql)
        ordering_check = _compare_text_clause(
            before=ordering_before,
            after=ordering_after,
            same_reason_code="SEMANTIC_ORDERING_STABLE",
            change_reason_code="SEMANTIC_ORDERING_CHANGED",
            missing_reason_code="SEMANTIC_ORDERING_ADDED_OR_REMOVED",
            missing_detail="order by clause added or removed",
            missing_status="UNCERTAIN",
            changed_status="UNCERTAIN",
        )
        pagination_before = _extract_pagination_clause(original_subject_sql)
        pagination_after = _extract_pagination_clause(rewritten_subject_sql)
        pagination_check = _compare_text_clause(
            before=pagination_before,
            after=pagination_after,
            same_reason_code="SEMANTIC_PAGINATION_STABLE",
            change_reason_code="SEMANTIC_PAGINATION_CHANGED",
            missing_reason_code="SEMANTIC_PAGINATION_ADDED_OR_REMOVED",
            missing_detail="pagination clause added or removed",
        )

        checks = {
            "predicate": predicate_check,
            "projection": projection_check,
            "ordering": ordering_check,
            "pagination": pagination_check,
        }

    check_statuses = [str((check or {}).get("status") or "UNCERTAIN").upper() for check in checks.values()]
    reasons = [str((check or {}).get("reasonCode") or "").strip() for check in checks.values()]
    reasons = [code for code in reasons if code]
    hard_conflicts = [
        str((check or {}).get("reasonCode") or "").strip()
        for check in checks.values()
        if str((check or {}).get("status") or "").upper() == "FAIL" and str((check or {}).get("reasonCode") or "").strip()
    ]

    if row_count_status == "MISMATCH":
        status = "FAIL"
        reasons.append("SEMANTIC_ROW_COUNT_MISMATCH")
        hard_conflicts.append("SEMANTIC_ROW_COUNT_MISMATCH")
    elif row_count_status in {"ERROR"}:
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_ERROR")
    elif checked is False or row_count_status in {"", "SKIPPED"}:
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_UNVERIFIED")
    elif "FAIL" in check_statuses:
        status = "FAIL"
    elif "UNCERTAIN" in check_statuses:
        status = "UNCERTAIN"
    else:
        status = "PASS"

    if status == "PASS" and row_count_status != "MATCH":
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_NOT_MATCH_CONFIRMED")

    if fingerprint_status == "MISMATCH":
        status = "FAIL"
        reasons.append("SEMANTIC_FINGERPRINT_MISMATCH")
        hard_conflicts.append("SEMANTIC_FINGERPRINT_MISMATCH")
    elif fingerprint_status == "MISMATCH_SAMPLE":
        if status == "PASS":
            status = "UNCERTAIN"
        reasons.append("SEMANTIC_FINGERPRINT_SAMPLE_MISMATCH")
    elif fingerprint_status == "ERROR":
        if status == "PASS":
            status = "UNCERTAIN"
        reasons.append("SEMANTIC_FINGERPRINT_ERROR")

    equivalence_override_applied = False
    equivalence_override_rule: str | None = None
    dml_noop_override_applied = False
    only_projection_uncertain = (
        str(projection_check.get("status") or "").upper() == "UNCERTAIN"
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "projection"
        )
    )
    only_predicate_uncertain = (
        str(predicate_check.get("status") or "").upper() == "UNCERTAIN"
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    )
    only_ordering_uncertain = (
        str(ordering_check.get("status") or "").upper() == "UNCERTAIN"
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "ordering"
        )
    )
    qualifier_only_uncertain_checks = {
        name
        for name, check in checks.items()
        if str((check or {}).get("status") or "").upper() == "UNCERTAIN"
        and (
            (name == "projection" and qualifier_only_projection_equivalent)
            or (name == "predicate" and _is_clause_qualifier_only_equivalent(predicate_before, predicate_after))
            or (name == "ordering" and _is_clause_qualifier_only_equivalent(ordering_before, ordering_after))
        )
    }
    if (
        status == "UNCERTAIN"
        and count_projection_equivalent
        and only_projection_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_COUNT_STAR_ONE"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_COUNT_EQUIVALENT",
            detail="count(1) and count(*) are treated as equivalent with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_top_level_and_order_equivalent(predicate_before, predicate_after)
        and only_predicate_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_CHANGED"}
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_PREDICATE_AND_ORDER"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_AND_ORDER_EQUIVALENT",
            detail="predicate only reorders top-level AND conjuncts with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PREDICATE_CHANGED"]
        hard_conflicts = [code for code in hard_conflicts if code != "SEMANTIC_PREDICATE_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and qualifier_only_projection_equivalent
        and only_projection_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_PROJECTION_QUALIFIER_ONLY"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_QUALIFIER_ONLY_EQUIVALENT",
            detail="projection change only removes single-table qualifiers with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_clause_qualifier_only_equivalent(predicate_before, predicate_after)
        and only_predicate_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_PREDICATE_QUALIFIER_ONLY"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_QUALIFIER_ONLY_EQUIVALENT",
            detail="predicate change only removes single-table qualifiers with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PREDICATE_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_clause_qualifier_only_equivalent(ordering_before, ordering_after)
        and only_ordering_uncertain
        and row_count_status == "MATCH"
        and order_sensitive_exact_evidence
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_ORDERING_QUALIFIER_ONLY"
        status = "PASS"
        checks["ordering"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_ORDERING_QUALIFIER_ONLY_EQUIVALENT",
            detail="ordering change only removes single-table qualifiers with exact DB fingerprint evidence",
            before=ordering_before,
            after=ordering_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_ORDERING_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and qualifier_only_uncertain_checks
        and {
            name
            for name, check in checks.items()
            if str((check or {}).get("status") or "").upper() == "UNCERTAIN"
        }
        == qualifier_only_uncertain_checks
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and ("ordering" not in qualifier_only_uncertain_checks or order_sensitive_exact_evidence)
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_SINGLE_TABLE_QUALIFIER_ONLY"
        status = "PASS"
        if "predicate" in qualifier_only_uncertain_checks:
            checks["predicate"] = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PREDICATE_QUALIFIER_ONLY_EQUIVALENT",
                detail="predicate change only removes single-table qualifiers with exact DB fingerprint evidence",
                before=predicate_before,
                after=predicate_after,
            )
            reasons = [code for code in reasons if code != "SEMANTIC_PREDICATE_CHANGED"]
        if "projection" in qualifier_only_uncertain_checks:
            checks["projection"] = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PROJECTION_QUALIFIER_ONLY_EQUIVALENT",
                detail="projection change only removes single-table qualifiers with exact DB fingerprint evidence",
                before=projection_before,
                after=projection_after,
            )
            reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        if "ordering" in qualifier_only_uncertain_checks:
            checks["ordering"] = _build_check(
                status="PASS",
                reason_code="SEMANTIC_ORDERING_QUALIFIER_ONLY_EQUIVALENT",
                detail="ordering change only removes single-table qualifiers with exact DB fingerprint evidence",
                before=ordering_before,
                after=ordering_after,
            )
            reasons = [code for code in reasons if code != "SEMANTIC_ORDERING_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "FAIL"
        and _is_boolean_tautology_only_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_BOOLEAN_TAUTOLOGY_REMOVAL"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_BOOLEAN_TAUTOLOGY_EQUIVALENT",
            detail="predicate only removes a tautology with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"]
        hard_conflicts = [code for code in hard_conflicts if code != "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_single_value_in_list_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_SINGLE_VALUE_IN_LIST"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_SINGLE_VALUE_IN_LIST_EQUIVALENT",
            detail="predicate only simplifies a single-value IN/NOT IN with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_constant_order_by_removed_equivalent(ordering_before, ordering_after)
        and row_count_status == "MATCH"
        and order_sensitive_exact_evidence
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_ORDERING_ADDED_OR_REMOVED", "SEMANTIC_ORDERING_CHANGED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "ordering"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_CONSTANT_ORDER_BY_REMOVAL"
        status = "PASS"
        checks["ordering"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_ORDERING_CONSTANT_ORDER_BY_EQUIVALENT",
            detail="ordering only removes a constant ORDER BY with exact DB fingerprint evidence",
            before=ordering_before,
            after=ordering_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_ORDERING_ADDED_OR_REMOVED", "SEMANTIC_ORDERING_CHANGED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_ORDERING_ADDED_OR_REMOVED", "SEMANTIC_ORDERING_CHANGED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_constant_order_by_removed_equivalent(ordering_before, ordering_after)
        and row_count_status in {"", "SKIPPED", "ERROR"}
        and fingerprint_status in {"", "SKIPPED", "ERROR"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "ordering"
        )
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_SAFE_BASELINE_CONSTANT_ORDER_BY_REMOVAL"
        status = "PASS"
        checks["ordering"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_ORDERING_CONSTANT_ORDER_BY_EQUIVALENT",
            detail="ordering only removes a constant ORDER BY and is treated as a safe structural baseline",
            before=ordering_before,
            after=ordering_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_ORDERING_ADDED_OR_REMOVED", "SEMANTIC_ORDERING_CHANGED", "SEMANTIC_ROW_COUNT_ERROR", "SEMANTIC_ROW_COUNT_UNVERIFIED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_same_column_or_to_in_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_OR_TO_IN"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_OR_TO_IN_EQUIVALENT",
            detail="predicate only rewrites same-column OR equality into IN with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_case_when_true_projection_equivalent(projection_before, projection_after)
        and only_projection_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_CASE_WHEN_TRUE"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_CASE_WHEN_TRUE_EQUIVALENT",
            detail="projection only simplifies CASE WHEN TRUE identity expression with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and _is_coalesce_identity_projection_equivalent(projection_before, projection_after)
        and only_projection_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_COALESCE_IDENTITY"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_COALESCE_IDENTITY_EQUIVALENT",
            detail="projection only simplifies COALESCE identity expression with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_constant_expression_folding_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_CONSTANT_EXPRESSION_FOLDING"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_CONSTANT_EXPRESSION_EQUIVALENT",
            detail="predicate only folds constant arithmetic expression with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_large_limit_removed_equivalent(pagination_before, pagination_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PAGINATION_ADDED_OR_REMOVED", "SEMANTIC_PAGINATION_CHANGED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "pagination"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_DB_EQUIVALENCE_LARGE_LIMIT_REMOVAL"
        status = "PASS"
        checks["pagination"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PAGINATION_LARGE_LIMIT_EQUIVALENT",
            detail="pagination only removes a large LIMIT with exact DB fingerprint evidence",
            before=pagination_before,
            after=pagination_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PAGINATION_ADDED_OR_REMOVED", "SEMANTIC_PAGINATION_CHANGED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PAGINATION_ADDED_OR_REMOVED", "SEMANTIC_PAGINATION_CHANGED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_null_comparison_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_DB_EQUIVALENCE_NULL_COMPARISON_NORMALIZATION"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_NULL_COMPARISON_EQUIVALENT",
            detail="predicate only normalizes NULL comparison with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_CHANGED", "SEMANTIC_PREDICATE_ADDED_OR_REMOVED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_distinct_on_equivalent(projection_before, projection_after, ordering_before, ordering_after)
        and row_count_status == "MATCH"
        and order_sensitive_exact_evidence
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PROJECTION_CHANGED", "SEMANTIC_ORDERING_CHANGED", "SEMANTIC_ORDERING_ADDED_OR_REMOVED"}
        and str((checks["predicate"] or {}).get("status") or "").upper() == "PASS"
        and str((checks["pagination"] or {}).get("status") or "").upper() == "PASS"
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_DISTINCT_ON_SIMPLIFICATION"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_DISTINCT_ON_EQUIVALENT",
            detail="projection only simplifies DISTINCT ON to DISTINCT on the same key with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        checks["ordering"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_ORDERING_DISTINCT_ON_EQUIVALENT",
            detail="ordering remains compatible with DISTINCT ON simplification",
            before=ordering_before,
            after=ordering_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PROJECTION_CHANGED", "SEMANTIC_ORDERING_CHANGED", "SEMANTIC_ORDERING_ADDED_OR_REMOVED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PROJECTION_CHANGED", "SEMANTIC_ORDERING_CHANGED", "SEMANTIC_ORDERING_ADDED_OR_REMOVED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_exists_self_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "predicate"
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_EXISTS_SELF_REWRITE"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_EXISTS_SELF_EQUIVALENT",
            detail="predicate only removes a self-correlated EXISTS identity filter with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        ]
        reasons.append(equivalence_override_rule)

    if (
        status in {"FAIL", "UNCERTAIN"}
        and _is_exists_to_in_equivalent(predicate_before, predicate_after)
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and set(code for code in hard_conflicts if code) <= {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        and str((checks["ordering"] or {}).get("status") or "").upper() == "PASS"
        and str((checks["pagination"] or {}).get("status") or "").upper() == "PASS"
        and (
            str((checks["projection"] or {}).get("status") or "").upper() == "PASS"
            or qualifier_only_projection_equivalent
        )
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_EXISTS_TO_IN_REWRITE"
        status = "PASS"
        checks["predicate"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PREDICATE_EXISTS_TO_IN_EQUIVALENT",
            detail="predicate rewrites EXISTS correlation into equivalent IN subquery with exact DB fingerprint evidence",
            before=predicate_before,
            after=predicate_after,
        )
        reasons = [
            code
            for code in reasons
            if code not in {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        ]
        hard_conflicts = [
            code
            for code in hard_conflicts
            if code not in {"SEMANTIC_PREDICATE_ADDED_OR_REMOVED", "SEMANTIC_PREDICATE_CHANGED"}
        ]
        if qualifier_only_projection_equivalent and str((checks["projection"] or {}).get("status") or "").upper() != "PASS":
            checks["projection"] = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PROJECTION_QUALIFIER_ONLY_EQUIVALENT",
                detail="projection change only adds single-table qualifiers alongside an EXISTS-to-IN equivalence with exact DB fingerprint evidence",
                before=projection_before,
                after=projection_after,
            )
            reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and is_dml_comparison
        and _normalize_sql(original_subject_sql) == _normalize_sql(rewritten_subject_sql)
        and all(str((check or {}).get("status") or "").upper() == "PASS" for check in checks.values())
        and row_count_status in {"", "SKIPPED", "ERROR"}
        and not hard_conflicts
    ):
        dml_noop_override_applied = True
        status = "PASS"
        reasons = [code for code in reasons if code not in {"SEMANTIC_ROW_COUNT_ERROR", "SEMANTIC_ROW_COUNT_UNVERIFIED"}]
        reasons.append("SEMANTIC_DML_NOOP_STABLE")

    safe_aggregation_wrapper_rule = _is_safe_aggregation_wrapper_equivalent(
        strip_sql_comments(original_sql),
        strip_sql_comments(rewritten_sql),
    )
    if (
        status == "UNCERTAIN"
        and safe_aggregation_wrapper_rule
        and all(str((check or {}).get("status") or "").upper() == "PASS" for check in checks.values())
        and row_count_status in {"", "SKIPPED", "ERROR"}
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = safe_aggregation_wrapper_rule
        status = "PASS"
        reasons = [code for code in reasons if code not in {"SEMANTIC_ROW_COUNT_ERROR", "SEMANTIC_ROW_COUNT_UNVERIFIED"}]
        reasons.append(safe_aggregation_wrapper_rule)

    if fingerprint_status in {"MATCH", "MISMATCH", "SAMPLE_MATCH", "MISMATCH_SAMPLE"}:
        evidence_level = "DB_FINGERPRINT"
    elif row_count_status in {"MATCH", "MISMATCH"}:
        evidence_level = "DB_COUNT"
    else:
        evidence_level = "STRUCTURE"
    base_evidence_level = "DB_COUNT" if row_count_status in {"MATCH", "MISMATCH"} else "STRUCTURE"
    confidence = _confidence_from_status_and_evidence_level(status=status, evidence_level=base_evidence_level)
    confidence_before_upgrade = confidence
    confidence_upgrade_applied = False
    confidence_upgrade_reasons: list[str] = []
    confidence_upgrade_sources: list[str] = []
    if not hard_conflicts:
        if fingerprint_strength == "EXACT":
            target = "HIGH" if status == "PASS" else "MEDIUM"
            if _confidence_rank(target) > _confidence_rank(confidence):
                confidence = target
                confidence_upgrade_applied = True
                confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_EXACT")
                confidence_upgrade_sources.append("DB_FINGERPRINT")
        elif fingerprint_strength == "PARTIAL":
            target = "MEDIUM"
            if _confidence_rank(target) > _confidence_rank(confidence):
                confidence = target
                confidence_upgrade_applied = True
                confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_PARTIAL")
                confidence_upgrade_sources.append("DB_FINGERPRINT")
    if dml_noop_override_applied and _confidence_rank("MEDIUM") > _confidence_rank(confidence):
        confidence = "MEDIUM"
        confidence_upgrade_applied = True
        confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DML_NOOP_STABLE")
        confidence_upgrade_sources.append("STRUCTURE")
    if safe_aggregation_wrapper_rule and status == "PASS" and _confidence_rank("MEDIUM") > _confidence_rank(confidence):
        confidence = "MEDIUM"
        confidence_upgrade_applied = True
        confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_AGGREGATION_SAFE_BASELINE")
        confidence_upgrade_sources.append("STRUCTURE")
    if (
        equivalence_override_rule == "SEMANTIC_SAFE_BASELINE_CONSTANT_ORDER_BY_REMOVAL"
        and status == "PASS"
        and _confidence_rank("MEDIUM") > _confidence_rank(confidence)
    ):
        confidence = "MEDIUM"
        confidence_upgrade_applied = True
        confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_CONSTANT_ORDER_BY_SAFE_BASELINE")
        confidence_upgrade_sources.append("STRUCTURE")

    evidence = {
        "checked": checked,
        "rowCountStatus": row_count_status or None,
        "fingerprintStatus": fingerprint_status,
        "fingerprintStrength": fingerprint_strength,
        "method": equivalence.get("method"),
        "evidenceRefs": [str(ref) for ref in (equivalence.get("evidenceRefs") or []) if str(ref).strip()],
        "evidenceRefObjects": [row for row in (equivalence.get("evidenceRefObjects") or []) if isinstance(row, dict)],
        "dbFingerprint": {
            "keySetStatus": key_set_status or "SKIPPED",
            "rowSampleStatus": row_sample_status or "SKIPPED",
            "strength": fingerprint_strength,
        },
    }
    coverage = {
        "structure": {
            "executedChecks": sorted(checks.keys()),
            "failedChecks": sorted(
                name for name, check in checks.items() if str((check or {}).get("status") or "").upper() == "FAIL"
            ),
            "uncertainChecks": sorted(
                name for name, check in checks.items() if str((check or {}).get("status") or "").upper() == "UNCERTAIN"
            ),
        },
        "data": {
            "rowCount": row_count_status or "SKIPPED",
            "fingerprint": fingerprint_status,
        },
    }

    dedup_reasons: list[str] = []
    for code in reasons:
        if code not in dedup_reasons:
            dedup_reasons.append(code)
    dedup_hard_conflicts: list[str] = []
    for code in hard_conflicts:
        if code and code not in dedup_hard_conflicts:
            dedup_hard_conflicts.append(code)

    return {
        "status": status,
        "confidence": confidence,
        "confidenceBeforeUpgrade": confidence_before_upgrade,
        "confidenceUpgradeApplied": confidence_upgrade_applied,
        "confidenceUpgradeReasons": confidence_upgrade_reasons,
        "confidenceUpgradeEvidenceSources": confidence_upgrade_sources,
        "equivalenceOverrideApplied": equivalence_override_applied,
        "equivalenceOverrideRule": equivalence_override_rule,
        "evidenceLevel": evidence_level,
        "checks": checks,
        "reasons": dedup_reasons,
        "hardConflicts": dedup_hard_conflicts,
        "coverage": coverage,
        "evidence": evidence,
    }
