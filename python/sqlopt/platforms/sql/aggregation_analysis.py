from __future__ import annotations

from dataclasses import dataclass, field
import re

from .canonicalization_support import (
    DISTINCT_DIRECT_RE,
    DISTINCT_WRAPPER_RE,
    GROUP_BY_WRAPPER_RE,
    HAVING_WRAPPER_RE,
    SELECT_DIRECT_RE,
    split_select_list,
)
from .template_rendering import normalize_sql_text

_SELECT_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)
_UNION_SPLIT_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)
_WINDOW_FN_RE = re.compile(r"([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*over\s*\(", flags=re.IGNORECASE)
_AGGREGATE_FN_RE = re.compile(r"\b(count|sum|avg|min|max)\s*\(", flags=re.IGNORECASE)
_SELECT_LIST_RE = re.compile(r"^\s*select\s+(?:distinct\s+)?(?P<select>.+?)\s+from\b", flags=re.IGNORECASE | re.DOTALL)
_CLAUSE_KEYWORDS = ("group by", "having", "order by", "limit", "offset", "fetch", "union all", "union")


@dataclass(frozen=True)
class AggregationQueryAnalysis:
    present: bool
    distinct_present: bool
    group_by_present: bool
    having_present: bool
    window_present: bool
    union_present: bool
    distinct_relaxation_candidate: bool
    group_by_columns: list[str] = field(default_factory=list)
    projection_expressions: list[str] = field(default_factory=list)
    aggregate_functions: list[str] = field(default_factory=list)
    having_expression: str | None = None
    order_by_expression: str | None = None
    limit_present: bool = False
    offset_present: bool = False
    window_functions: list[str] = field(default_factory=list)
    union_branches: int | None = None
    blockers: list[str] = field(default_factory=list)
    capability_profile: dict[str, object] = field(default_factory=dict)


def _extract_select_list(sql: str) -> list[str]:
    match = _SELECT_LIST_RE.match(sql)
    if match is None:
        return []
    return split_select_list(normalize_sql_text(match.group("select")))


def _clause_positions(sql: str) -> list[tuple[str, int]]:
    lowered = sql.lower()
    positions: list[tuple[str, int]] = []
    depth = 0
    in_single = False
    in_double = False
    idx = 0
    while idx < len(lowered):
        ch = lowered[idx]
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif depth == 0:
                for keyword in _CLAUSE_KEYWORDS:
                    if lowered.startswith(keyword, idx):
                        before_ok = idx == 0 or not lowered[idx - 1].isalnum()
                        after_idx = idx + len(keyword)
                        after_ok = after_idx >= len(lowered) or not lowered[after_idx].isalnum()
                        if before_ok and after_ok:
                            positions.append((keyword, idx))
                            idx = after_idx - 1
                            break
        idx += 1
    return positions


def _extract_top_level_clause(sql: str, keyword: str) -> str | None:
    positions = _clause_positions(sql)
    start = next((pos for name, pos in positions if name == keyword), None)
    if start is None:
        return None
    end = len(sql)
    clause_end = start + len(keyword)
    for _, pos in positions:
        if pos > start and pos < end:
            end = pos
    expr = normalize_sql_text(sql[clause_end:end])
    return expr or None


def _top_level_keyword_present(sql: str, keyword: str) -> bool:
    return any(name == keyword for name, _ in _clause_positions(sql))


def _top_level_union_branches(sql: str) -> int | None:
    positions = [pos for name, pos in _clause_positions(sql) if name in {"union", "union all"}]
    if not positions:
        return None
    return len(positions) + 1


def _dedupe_upper(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        normalized = str(value or "").strip().upper()
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _extract_simple_wrapper_inner_from(sql: str) -> str | None:
    wrapper_match = GROUP_BY_WRAPPER_RE.match(sql)
    if wrapper_match is None:
        return None
    return normalize_sql_text(wrapper_match.group("inner_from"))


def _safe_baseline_family(original_sql: str, rewritten_sql: str) -> str | None:
    if DISTINCT_WRAPPER_RE.match(original_sql) and DISTINCT_DIRECT_RE.match(rewritten_sql):
        return "REDUNDANT_DISTINCT_WRAPPER"
    having_wrapper = HAVING_WRAPPER_RE.match(original_sql)
    if having_wrapper is not None and SELECT_DIRECT_RE.match(rewritten_sql):
        inner_from = normalize_sql_text(having_wrapper.group("inner_from"))
        if _extract_top_level_clause(inner_from, "having"):
            return "REDUNDANT_HAVING_WRAPPER"
    group_by_wrapper = GROUP_BY_WRAPPER_RE.match(original_sql)
    if group_by_wrapper is not None and SELECT_DIRECT_RE.match(rewritten_sql):
        inner_from = normalize_sql_text(group_by_wrapper.group("inner_from"))
        if _extract_top_level_clause(inner_from, "group by") and not _extract_top_level_clause(inner_from, "having"):
            return "REDUNDANT_GROUP_BY_WRAPPER"
    return None


def _shape_family(
    *,
    distinct_present: bool,
    group_by_present: bool,
    having_present: bool,
    window_present: bool,
    union_present: bool,
) -> str:
    if union_present:
        return "UNION"
    if window_present:
        return "WINDOW"
    if having_present:
        return "HAVING"
    if group_by_present:
        return "GROUP_BY"
    if distinct_present:
        return "DISTINCT"
    return "NONE"


def _constraint_family(
    *,
    safe_baseline_family: str | None,
    distinct_relaxation_candidate: bool,
    distinct_present: bool,
    group_by_present: bool,
    having_present: bool,
    window_present: bool,
    union_present: bool,
) -> str:
    if safe_baseline_family:
        return "SAFE_BASELINE"
    if distinct_relaxation_candidate:
        return "DISTINCT_RELAXATION"
    if union_present:
        return "UNION_AGGREGATION"
    if window_present:
        return "WINDOW_AGGREGATION"
    if having_present:
        return "HAVING_AGGREGATION"
    if group_by_present:
        return "GROUP_BY_AGGREGATION"
    if distinct_present:
        return "DISTINCT_AGGREGATION"
    return "NONE"


def analyze_aggregation_query(original_sql: str, rewritten_sql: str) -> AggregationQueryAnalysis:
    original_normalized = normalize_sql_text(original_sql)
    rewritten_normalized = normalize_sql_text(rewritten_sql)
    inner_from = _extract_simple_wrapper_inner_from(original_normalized)
    aggregate_scope = inner_from or original_normalized

    distinct_present = bool(_SELECT_DISTINCT_RE.search(original_normalized))
    group_by_expression = _extract_top_level_clause(aggregate_scope, "group by")
    having_expression = _extract_top_level_clause(aggregate_scope, "having")
    order_by_expression = _extract_top_level_clause(original_normalized, "order by")
    projection_expressions = _extract_select_list(original_normalized)
    group_by_columns = split_select_list(group_by_expression or "")
    window_functions = _dedupe_upper(_WINDOW_FN_RE.findall(aggregate_scope))
    aggregate_functions = _dedupe_upper(
        _AGGREGATE_FN_RE.findall(" ".join(projection_expressions + ([having_expression] if having_expression else [])))
    )
    union_branches = _top_level_union_branches(aggregate_scope)

    group_by_present = bool(group_by_expression)
    having_present = bool(having_expression)
    window_present = bool(window_functions)
    union_present = union_branches is not None and union_branches > 1
    limit_present = _top_level_keyword_present(aggregate_scope, "limit")
    offset_present = _top_level_keyword_present(aggregate_scope, "offset")

    blockers: list[str] = []
    if distinct_present:
        blockers.append("DISTINCT_PRESENT")
    if group_by_present:
        blockers.append("GROUP_BY_PRESENT")
    if having_present:
        blockers.append("HAVING_PRESENT")
    if window_present:
        blockers.append("WINDOW_PRESENT")
    if union_present:
        blockers.append("UNION_PRESENT")

    safe_baseline_family = _safe_baseline_family(original_normalized, rewritten_normalized)
    shape_family = _shape_family(
        distinct_present=distinct_present,
        group_by_present=group_by_present,
        having_present=having_present,
        window_present=window_present,
        union_present=union_present,
    )
    constraint_family = _constraint_family(
        safe_baseline_family=safe_baseline_family,
        distinct_relaxation_candidate=bool(distinct_present and not _SELECT_DISTINCT_RE.search(rewritten_normalized)),
        distinct_present=distinct_present,
        group_by_present=group_by_present,
        having_present=having_present,
        window_present=window_present,
        union_present=union_present,
    )
    capability_tier = "SAFE_BASELINE" if safe_baseline_family else ("NONE" if shape_family == "NONE" else "REVIEW_REQUIRED")

    return AggregationQueryAnalysis(
        present=bool(blockers),
        distinct_present=distinct_present,
        group_by_present=group_by_present,
        having_present=having_present,
        window_present=window_present,
        union_present=union_present,
        distinct_relaxation_candidate=bool(distinct_present and not _SELECT_DISTINCT_RE.search(rewritten_normalized)),
        group_by_columns=group_by_columns,
        projection_expressions=projection_expressions,
        aggregate_functions=aggregate_functions,
        having_expression=having_expression,
        order_by_expression=order_by_expression,
        limit_present=limit_present,
        offset_present=offset_present,
        window_functions=window_functions,
        union_branches=union_branches,
        blockers=blockers,
        capability_profile={
            "shapeFamily": shape_family,
            "capabilityTier": capability_tier,
            "constraintFamily": constraint_family,
            "safeBaselineFamily": safe_baseline_family,
            "wrapperFlattenCandidate": bool(safe_baseline_family),
            "directRelaxationCandidate": bool(distinct_present and not _SELECT_DISTINCT_RE.search(rewritten_normalized)),
            "blockers": list(blockers),
        },
    )
