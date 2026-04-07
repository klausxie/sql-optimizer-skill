from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .candidate_generation_models import (
    CandidateGenerationDiagnostics,
    CandidateGenerationOutcome,
    LowValueAssessment,
)
from .candidate_generation_support import (
    classify_blocked_shape,
    distinct_on_cleanup_sql,
    limit_large_cleanup_sql,
    recover_candidates_from_shape,
    recover_candidates_from_text,
)


# Regex patterns used in low-value assessment
_IDENTITY_STRATEGIES = {
    "none",
    "index_scan",
    "structure_preserving",
    "no_optimization_needed",
}

# Aggregation patterns
_AGGREGATION_RE = re.compile(r"\bgroup\s+by\b|\bhaving\b", flags=re.IGNORECASE)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", flags=re.IGNORECASE)

# DML patterns
_UPDATE_RE = re.compile(r"^\s*update\b", flags=re.IGNORECASE)
_DELETE_RE = re.compile(r"^\s*delete\b", flags=re.IGNORECASE)
_DML_PARAM_SUBSTITUTION_RE = re.compile(r"parameter_substitution|batch_optimization|null_safe|array_parameter", flags=re.IGNORECASE)
_MYBATIS_TAG_RE = re.compile(r"<set\s|<if\s|<foreach\s|<where\s|<set>|<if>|<foreach>|<where>", flags=re.IGNORECASE)

# Window patterns
_WINDOW_RE = re.compile(r"\bover\s*\(", flags=re.IGNORECASE)

# Distinct patterns
_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)

# Union patterns
_UNION_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)

# Low-value rewrite strategies
_LOW_VALUE_STRATEGIES = frozenset([
    "remove_redundant_order_by",
    "remove_redundant_group_by_order_by",
    "replace_distinct_with_group_by",
    "replace_distinct_with_group_by_index_scan",
    "remove_having_index_hint",
    "extract_window_function",
    "dml_speculative",
    "dml_parameter_substitution",
    "dml_batch_optimization",
    "null_safe_update",
    "array_parameter_update",
    "foreach_template_fix",
    "foreach_dynamic_sql_fix",
    "foreach_fix_syntax",
    "add_limit_only",
    "add_offset_only",
    "add_limit_and_offset",
])

# Strategies that indicate aggregation transform
_AGGREGATION_TRANSFORM_STRATEGIES = frozenset([
    "remove_redundant_order_by",
    "remove_redundant_group_by_order_by",
    "replace_distinct_with_group_by",
    "replace_distinct_with_group_by_index_scan",
    "remove_having_index_hint",
    "aggregation_transform",
])

# Strategies that indicate window rewrite
_WINDOW_STRATEGIES = frozenset([
    "extract_window_function",
    "window_function_extract",
    "remove_window",
])

# Strategies for static include with LIMIT
_STATIC_INCLUDE_LIMIT_STRATEGIES = frozenset([
    "add_limit_only",
    "add_offset_only",
    "add_limit_and_offset",
    "add_pagination",
    "explicit_pagination_offset",
    "add_pagination_offset",
    "static_include_limit",
    "static_include_paged",
])

_DYNAMIC_FILTER_FEATURES = {"WHERE", "IF", "CHOOSE", "TRIM", "BIND"}
_HINT_RE = re.compile(r"/\*\+\s*.+?\*/", flags=re.IGNORECASE | re.DOTALL)
_HINT_STRATEGY_RE = re.compile(r"index|hint", flags=re.IGNORECASE)
_ORDER_STRATEGY_RE = re.compile(r"order", flags=re.IGNORECASE)
_TIME_FILTER_STRATEGY_RE = re.compile(r"time[_ ]?filter", flags=re.IGNORECASE)
_JOIN_REWRITE_STRATEGY_RE = re.compile(
    r"driving[_ ]?table|join[_ ]?reorder|reorder[_ ]?join|join[_ ]?order|push.*join",
    flags=re.IGNORECASE,
)
_PREDICATE_REWRITE_STRATEGY_RE = re.compile(
    r"predicate[_ ]?simplification|ilike[_ ]?to[_ ]?like|standardize[_ ]?ilike|standardize[_ ]?like|simplify[_ ]?or|or[_ ]|coalesce[_ ]?null[_ ]?handling|coalesce|redundant[_ ]?condition[_ ]?optimization|redundant[_ ]?condition",
    flags=re.IGNORECASE,
)
_COUNT_REWRITE_STRATEGY_RE = re.compile(r"count[_ ]?to[_ ]?exists|exists", flags=re.IGNORECASE)
_WITH_RE = re.compile(r"^\s*with\b", flags=re.IGNORECASE)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", flags=re.IGNORECASE)
_UNION_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\b|\bfetch\s+first\b", flags=re.IGNORECASE)
_JOIN_SUBQUERY_RE = re.compile(r"\bjoin\s*\(\s*select\b", flags=re.IGNORECASE)
_FROM_SUBQUERY_RE = re.compile(r"\bfrom\s*\(\s*select\b", flags=re.IGNORECASE)
_JOIN_CLAUSE_RE = re.compile(r"\bjoin\b.+?\bon\b(?P<on_clause>.+?)(?=\bjoin\b|\bwhere\b|\border\s+by\b|\blimit\b|\boffset\b|$)", flags=re.IGNORECASE | re.DOTALL)
_QUALIFIER_ONLY_STRATEGY_RE = re.compile(r"qualification|qualifier|alias", flags=re.IGNORECASE)
_SINGLE_TABLE_QUALIFIER_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.")
_FROM_ALIAS_RE = re.compile(
    r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(?!where\b|order\b|group\b|limit\b|offset\b|join\b)([a-zA-Z_][a-zA-Z0-9_]*)\b",
    flags=re.IGNORECASE,
)


def _normalize_sql(value: str) -> str:
    """Normalize SQL for comparison."""
    return " ".join(str(value or "").split())


def _extract_on_clauses(sql: str) -> list[str]:
    return [_normalize_sql(match.group("on_clause") or "") for match in _JOIN_CLAUSE_RE.finditer(sql or "")]


def _strip_single_table_qualifiers(sql: str) -> str:
    without_qualifiers = _SINGLE_TABLE_QUALIFIER_RE.sub("", sql or "")
    without_alias = _FROM_ALIAS_RE.sub(r"FROM \1", without_qualifiers)
    return _normalize_sql(without_alias)


def _is_single_table_qualifier_only_rewrite(original_sql: str, rewritten_sql: str) -> bool:
    normalized_original = _normalize_sql(original_sql)
    normalized_rewritten = _normalize_sql(rewritten_sql)
    if normalized_original == normalized_rewritten:
        return False
    if _JOIN_REWRITE_STRATEGY_RE.search(normalized_original) or _JOIN_REWRITE_STRATEGY_RE.search(normalized_rewritten):
        return False
    if " join " in normalized_original.lower() or " join " in normalized_rewritten.lower():
        return False
    return _strip_single_table_qualifiers(normalized_original) == _strip_single_table_qualifiers(normalized_rewritten)


def _dynamic_filter_features(sql_unit: dict[str, Any]) -> set[str]:
    features = {
        str(row).strip().upper()
        for row in (sql_unit.get("dynamicFeatures") or [])
        if str(row).strip()
    }
    trace = dict(sql_unit.get("dynamicTrace") or {})
    for row in (trace.get("statementFeatures") or []):
        feature = str(row).strip().upper()
        if feature:
            features.add(feature)
    return features


@dataclass
class CandidateGenerationContext:
    """Context for candidate generation evaluation."""
    sql_key: str
    original_sql: str
    sql_unit: dict[str, Any]
    trace: dict[str, Any]


def _all_text_fallback(raw_candidates: list[dict[str, Any]]) -> bool:
    return bool(raw_candidates) and all(
        str(row.get("rewriteStrategy") or "").strip() == "opencode_text_fallback"
        for row in raw_candidates
    )


# ===== 独立的低值候选检测器 =====

def _check_text_fallback(candidate: dict[str, Any]) -> LowValueAssessment | None:
    """检测 text fallback（ diagnostics only）"""
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    if strategy == "opencode_text_fallback":
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="CANONICAL_NOOP_HINT",
            category="CANONICAL_NOOP_HINT",
            reason="text fallback is diagnostics only and not a consumable sql candidate",
        )
    return None


def _check_empty_sql(candidate: dict[str, Any]) -> LowValueAssessment | None:
    """检测空 SQL"""
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
    if not rewritten_sql:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="IDENTITY_NOOP",
            category="IDENTITY_NOOP",
            reason="candidate has no rewritten sql",
        )
    return None


def _check_identity(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测恒等变换（SQL 无实质改变）"""
    from .canonicalization_support import normalize_sql
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    norm_original = _normalize_sql(context.original_sql)
    norm_rewritten = _normalize_sql(rewritten_sql)
    if norm_rewritten == norm_original:
        if strategy in _IDENTITY_STRATEGIES or not strategy:
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id="IDENTITY_NOOP",
                category="IDENTITY_NOOP",
                reason="candidate is structurally identical to the original sql",
            )
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="CANONICAL_NOOP_HINT",
            category="CANONICAL_NOOP_HINT",
            reason="candidate only restates the original sql without a material change",
        )
    return None


def _check_comment_only(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测仅注释变更"""
    from .canonicalization_support import normalize_sql, strip_sql_comments
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()

    def _comment_stripped_normalized_sql(value: str) -> str:
        return normalize_sql(strip_sql_comments(value))

    original_sql = context.original_sql
    if _comment_stripped_normalized_sql(rewritten_sql) != _comment_stripped_normalized_sql(original_sql):
        return None  # continue checking
    if normalize_sql(rewritten_sql) != normalize_sql(original_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="COMMENT_ONLY_REWRITE",
            category="CANONICAL_NOOP_HINT",
            reason="candidate only changes sql comments or annotations without a material sql change",
        )
    return None


def _check_dynamic_filter(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测动态过滤器的投机重写"""
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    original_sql = context.original_sql

    features = _dynamic_filter_features(context.sql_unit)
    if not (features & _DYNAMIC_FILTER_FEATURES):
        return None

    norm_original = _normalize_sql(original_sql)
    norm_rewritten = _normalize_sql(rewritten_sql)

    # Check hint additions
    if _HINT_RE.search(rewritten_sql) or _HINT_STRATEGY_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate adds optimizer hints on a dynamic filter template without a stable template-preserving rewrite",
        )

    # Check predicate appending
    if norm_rewritten.startswith(f"{norm_original} AND ") or norm_rewritten.startswith(f"{norm_original} OR "):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate appends speculative predicates on a dynamic filter template",
        )

    # Check pagination appending
    if norm_rewritten.startswith(f"{norm_original} LIMIT ") or norm_rewritten.startswith(f"{norm_original} FETCH "):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate appends speculative pagination on a dynamic filter template",
        )

    # Check LIMIT introduction
    if _LIMIT_RE.search(norm_rewritten) and not _LIMIT_RE.search(norm_original):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces pagination on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check time filter strategy
    if _TIME_FILTER_STRATEGY_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces a time-based filter on a dynamic filter template without a safe template-preserving rewrite",
        )

    # Check ORDER BY introduction
    if _ORDER_BY_RE.search(norm_rewritten) and not _ORDER_BY_RE.search(norm_original):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate adds ordering on a dynamic filter template without a safe template-preserving rewrite",
        )

    # Check order strategy
    if _ORDER_STRATEGY_RE.search(strategy) and norm_rewritten != norm_original:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate alters ordering on a dynamic filter template without a safe template-preserving rewrite",
        )

    if _QUALIFIER_ONLY_STRATEGY_RE.search(strategy) and _is_single_table_qualifier_only_rewrite(original_sql, rewritten_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_QUALIFIER_ONLY_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate only adds or removes single-table qualifiers on a dynamic filter template; prefer safe baseline recovery",
        )

    # Check join rewrite strategy
    if _JOIN_REWRITE_STRATEGY_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces a join-order or join-predicate rewrite on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check predicate rewrite strategy
    if _PREDICATE_REWRITE_STRATEGY_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate rewrites dynamic filter predicates without a safe template-preserving baseline",
        )

    # Check count rewrite
    if _COUNT_REWRITE_STRATEGY_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate rewrites count semantics on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check CTE introduction
    if _WITH_RE.search(norm_rewritten) and not _WITH_RE.search(norm_original):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces a CTE-based structural rewrite on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check UNION introduction
    if _UNION_RE.search(norm_rewritten) and not _UNION_RE.search(norm_original):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces a UNION-based structural rewrite on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check subquery pushdown
    if (
        (_JOIN_SUBQUERY_RE.search(norm_rewritten) or _FROM_SUBQUERY_RE.search(norm_rewritten))
        and not (_JOIN_SUBQUERY_RE.search(norm_original) or _FROM_SUBQUERY_RE.search(norm_original))
    ):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate introduces a subquery pushdown rewrite on a dynamic filter template without a safe template-preserving baseline",
        )

    # Check dynamic filter in ON clause
    original_on_clauses = _extract_on_clauses(norm_original)
    rewritten_on_clauses = _extract_on_clauses(norm_rewritten)
    if (
        rewritten_on_clauses
        and any("#{" in clause for clause in rewritten_on_clauses)
        and not any("#{" in clause for clause in original_on_clauses)
    ):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
            reason="candidate pushes dynamic filter predicates into join conditions without a safe template-preserving baseline",
        )

    return None


def _check_aggregation_transform(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测聚合转换"""
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    original_sql = context.original_sql
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()

    # Check aggregation transforms (removing ORDER BY from GROUP BY)
    if strategy in _AGGREGATION_TRANSFORM_STRATEGIES and _AGGREGATION_RE.search(original_sql):
        if _ORDER_BY_RE.search(original_sql) and not _ORDER_BY_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id="AGGREGATION_TRANSFORM",
                category="AGGREGATION_TRANSFORM",
                reason="candidate removes ORDER BY from aggregation query without proven performance benefit",
            )

    # Check speculative filter/predicate additions on aggregation queries
    if "add_filter" in strategy_lower or "add_limit" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="SPECULATIVE_AGGREGATE_ADDITION",
            category="SPECULATIVE_AGGREGATE_ADDITION",
            reason="candidate adds speculative filter or limit to aggregation query without safe baseline",
        )

    # Check window function extraction
    if "window" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="WINDOW_FUNCTION_EXTRACT",
            category="WINDOW_FUNCTION_EXTRACT",
            reason="candidate extracts window function without safe template-preserving baseline",
        )

    return None


def _check_dml_speculative(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测 DML 投机重写"""
    original_sql = context.original_sql
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()

    if not (_UPDATE_RE.search(original_sql) or _DELETE_RE.search(original_sql)):
        return None

    if _DML_PARAM_SUBSTITUTION_RE.search(strategy):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DML_SPECULATIVE",
            category="DML_SPECULATIVE",
            reason="candidate applies speculative DML optimization without safe baseline",
        )

    if _MYBATIS_TAG_RE.search(rewritten_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DML_SPECULATIVE",
            category="DML_SPECULATIVE",
            reason="candidate introduces MyBatis tags in DML without safe baseline",
        )

    return None


def _check_static_include(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测静态包含的投机分页"""
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    sql_unit = context.sql_unit or {}
    dynamic_features = set(str(x).upper() for x in sql_unit.get("dynamicFeatures", []))

    if "INCLUDE" not in dynamic_features:
        return None

    if any(x in strategy_lower for x in ["index", "filter", "time_", "paged", "page", "offset"]):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_INCLUDE_SPECULATIVE_PAGINATION",
            category="STATIC_INCLUDE_SPECULATIVE_PAGINATION",
            reason="candidate adds speculative filter/index to static include without safe template-preserving baseline",
        )

    return None


def _check_static_statement(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """Detect speculative rewrites on plain static statements."""
    sql_unit = context.sql_unit or {}
    dynamic_features = set(str(x).upper() for x in sql_unit.get("dynamicFeatures", []))
    if dynamic_features:
        return None

    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    original_sql = _normalize_sql(context.original_sql)
    rewritten_sql = _normalize_sql(str(candidate.get("rewrittenSql") or ""))
    expected_limit_cleanup = limit_large_cleanup_sql(original_sql)
    expected_distinct_on_cleanup = distinct_on_cleanup_sql(original_sql)

    if expected_limit_cleanup is not None and _normalize_sql(expected_limit_cleanup) != rewritten_sql:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_LIMIT_LARGE_SPECULATIVE_REWRITE",
            category="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            reason="candidate changes a large-LIMIT statement without using the safe baseline limit removal",
        )

    if expected_distinct_on_cleanup is not None and _normalize_sql(expected_distinct_on_cleanup) != rewritten_sql:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_DISTINCT_ON_SPECULATIVE_REWRITE",
            category="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            reason="candidate changes a DISTINCT ON statement without using the safe baseline distinct simplification",
        )

    if _QUALIFIER_ONLY_STRATEGY_RE.search(strategy) and _is_single_table_qualifier_only_rewrite(original_sql, rewritten_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_STATEMENT_QUALIFIER_ONLY_REWRITE",
            category="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            reason="candidate only changes single-table qualifiers or aliases on a static statement; prefer safe baseline cleanup",
        )

    if (
        _PREDICATE_REWRITE_STRATEGY_RE.search(strategy)
        or "filter" in strategy_lower
        or "predicate" in strategy_lower
        or (" where " in rewritten_sql.lower() and " where " not in original_sql.lower())
    ) and " where " not in original_sql.lower():
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            category="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            reason="candidate introduces a speculative predicate rewrite on a static statement without a safe baseline",
        )

    if (_LIMIT_RE.search(rewritten_sql) and not _LIMIT_RE.search(original_sql)) or "limit" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            category="STATIC_STATEMENT_SPECULATIVE_REWRITE",
            reason="candidate introduces speculative pagination on a static statement without a safe baseline",
        )

    return None


def _check_other_patterns(candidate: dict[str, Any], context: CandidateGenerationContext) -> LowValueAssessment | None:
    """检测其他模式：distinct, union, foreach, parameter 等"""
    strategy = str(candidate.get("rewriteStrategy") or "").strip()
    strategy_lower = strategy.lower()
    original_sql = context.original_sql
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()

    # Check distinct to group by transform
    if "distinct" in strategy.lower() and _DISTINCT_RE.search(original_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DISTINCT_TRANSFORM",
            category="DISTINCT_TRANSFORM",
            reason="candidate rewrites DISTINCT without proven performance benefit",
        )

    # Check union simplification
    if "union" in strategy_lower and _UNION_RE.search(original_sql):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="UNION_SIMPLIFICATION",
            category="UNION_SIMPLIFICATION",
            reason="candidate simplifies UNION without safe template-preserving baseline",
        )

    # Check distinct transformation
    if "distinct" in strategy_lower or (_DISTINCT_RE.search(original_sql) and "group by" in rewritten_sql.lower()):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="DISTINCT_TRANSFORM",
            category="DISTINCT_TRANSFORM",
            reason="candidate rewrites DISTINCT without proven performance benefit",
        )

    # Check array parameter conversion
    if "array" in strategy_lower or "single_value" in strategy_lower or "in_to" in strategy_lower or "any(" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="ARRAY_PARAMETER_CONVERSION",
            category="ARRAY_PARAMETER_CONVERSION",
            reason="candidate converts array parameter without safe baseline",
        )

    # Check parameter/template fix strategies
    if "parameter" in strategy_lower or "template_fix" in strategy_lower or "syntax" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="PARAMETER_TEMPLATE_FIX",
            category="PARAMETER_TEMPLATE_FIX",
            reason="candidate applies parameter or template fix without safe baseline",
        )

    # Check condition/equality/placeholder strategies
    if "specify_condition" in strategy_lower or "single_placeholder" in strategy_lower or "placeholder_equality" in strategy_lower or "explicit_column" in strategy_lower or "simplify_in" in strategy_lower:
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="CONDITION_PLACEHOLDER_FIX",
            category="CONDITION_PLACEHOLDER_FIX",
            reason="candidate applies condition or placeholder fix without safe baseline",
        )

    # Check IN ( to = conversion (semantic change)
    if re.search(r"\bin\s*\(", original_sql, re.IGNORECASE) and re.search(r"\b=\s*#\{", rewritten_sql, re.IGNORECASE):
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="IN_TO_EQUAL_CONVERSION",
            category="IN_TO_EQUAL_CONVERSION",
            reason="candidate converts IN to = which changes semantics",
        )

    # Check foreach template fixes
    if "foreach" in strategy.lower():
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="FOREACH_TEMPLATE_FIX",
            category="FOREACH_TEMPLATE_FIX",
            reason="candidate applies foreach template fix without safe baseline",
        )

    return None


def _is_low_value_candidate(
    context: CandidateGenerationContext,
    candidate: dict[str, Any],
) -> LowValueAssessment | None:
    """Check if a candidate is low-value (not worth applying).

    Returns the assessment if low-value, None otherwise.
    """
    # 1. Check text fallback first (quick exit)
    result = _check_text_fallback(candidate)
    if result:
        return result

    # 2. Check empty SQL
    result = _check_empty_sql(candidate)
    if result:
        return result

    # 3. Check identity (no change)
    result = _check_identity(candidate, context)
    if result:
        return result

    # 4. Check comment-only changes
    result = _check_comment_only(candidate, context)
    if result:
        return result

    # 5. Check dynamic filter speculative rewrites
    result = _check_dynamic_filter(candidate, context)
    if result:
        return result

    # 6. Check aggregation transforms
    result = _check_aggregation_transform(candidate, context)
    if result:
        return result

    # 7. Check DML speculative
    result = _check_dml_speculative(candidate, context)
    if result:
        return result

    # 8. Check static include
    result = _check_static_include(candidate, context)
    if result:
        return result

    # 9. Check static statement
    result = _check_static_statement(candidate, context)
    if result:
        return result

    # 10. Check other patterns
    result = _check_other_patterns(candidate, context)
    if result:
        return result

    # Not low-value
    return None


def _collect_low_value_assessments(
    context: CandidateGenerationContext,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[LowValueAssessment]]:
    accepted: list[dict[str, Any]] = []
    assessments: list[LowValueAssessment] = []
    for candidate in candidates:
        assessment = _is_low_value_candidate(context, candidate)
        if assessment is not None:
            assessments.append(assessment)
        else:
            accepted.append(candidate)
    return accepted, assessments


def _recover_candidates(
    context: CandidateGenerationContext,
    degraded_kind: str,
    raw_candidates: list[dict[str, Any]],
    accepted_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attempt to recover candidates from degradation."""
    if accepted_candidates:
        return []

    sql_key = context.sql_key
    original_sql = context.original_sql

    if degraded_kind == "TEXT_ONLY_FALLBACK":
        text = str(((raw_candidates[0] or {}).get("rewrittenSql")) or "")
        candidates = recover_candidates_from_text(sql_key, original_sql, text)
        return candidates

    if degraded_kind in {"EMPTY_CANDIDATES", "ONLY_LOW_VALUE_CANDIDATES"}:
        candidates = recover_candidates_from_shape(sql_key, original_sql)
        return candidates

    return []


def _prefer_order_preserving_safe_baseline_recovery(
    context: CandidateGenerationContext,
    accepted_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not accepted_candidates:
        return []

    original_sql = context.original_sql
    if not _ORDER_BY_RE.search(_normalize_sql(original_sql)):
        return []

    risky_order_drop = False
    for candidate in accepted_candidates:
        rewritten_sql = _normalize_sql(str(candidate.get("rewrittenSql") or ""))
        if not _ORDER_BY_RE.search(rewritten_sql):
            risky_order_drop = True
            break
    if not risky_order_drop:
        return []

    recovered = recover_candidates_from_shape(context.sql_key, original_sql)
    if not recovered:
        return []
    first_strategy = str((recovered[0] or {}).get("rewriteStrategy") or "").strip().upper()
    if first_strategy != "REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED":
        return []
    return recovered


def evaluate_candidate_generation(
    *,
    sql_key: str,
    original_sql: str,
    sql_unit: dict[str, Any],
    raw_candidates: list[dict[str, Any]],
    valid_candidates: list[dict[str, Any]],
    trace: dict[str, Any],
) -> CandidateGenerationOutcome:
    context = CandidateGenerationContext(
        sql_key=sql_key,
        original_sql=original_sql,
        sql_unit=sql_unit,
        trace=trace,
    )
    accepted_candidates, low_value_assessments = _collect_low_value_assessments(context, valid_candidates)

    diagnostics = CandidateGenerationDiagnostics(
        raw_candidate_count=len(raw_candidates),
        validated_candidate_count=len(valid_candidates),
        accepted_candidate_count=len(accepted_candidates),
        pruned_low_value_count=len(low_value_assessments),
        low_value_candidate_count=len(low_value_assessments),
        raw_rewrite_strategies=[str(row.get("rewriteStrategy") or "") for row in raw_candidates],
        final_candidate_count=len(accepted_candidates),
        low_value_assessments=low_value_assessments,
    )

    degraded_kind: str | None = None
    if _all_text_fallback(raw_candidates):
        degraded_kind = "TEXT_ONLY_FALLBACK"
    elif not valid_candidates:
        degraded_kind = "EMPTY_CANDIDATES"
    elif valid_candidates and not accepted_candidates and low_value_assessments:
        degraded_kind = "ONLY_LOW_VALUE_CANDIDATES"

    diagnostics.degradation_kind = degraded_kind
    if degraded_kind is None:
        preferred_recovery = _prefer_order_preserving_safe_baseline_recovery(context, accepted_candidates)
        if preferred_recovery:
            diagnostics.recovery_attempted = True
            diagnostics.recovery_reason = "SAFE_BASELINE_ORDER_PRESERVING_RECOVERY"
            diagnostics.recovery_strategy = str((preferred_recovery[0] or {}).get("rewriteStrategy") or "SHAPE_RECOVERY")
            diagnostics.recovered_candidate_count = len(preferred_recovery)
            return CandidateGenerationOutcome(
                accepted_candidates=accepted_candidates,
                recovery_candidates=preferred_recovery,
                diagnostics=diagnostics,
            )
        diagnostics.recovery_reason = "NONE"
        return CandidateGenerationOutcome(
            accepted_candidates=accepted_candidates,
            recovery_candidates=[],
            diagnostics=diagnostics,
        )

    diagnostics.recovery_attempted = True
    if degraded_kind == "ONLY_LOW_VALUE_CANDIDATES":
        diagnostics.recovery_reason = "LOW_VALUE_PRUNED_TO_EMPTY"
    elif degraded_kind == "EMPTY_CANDIDATES":
        trace_degrade_reason = str(trace.get("degrade_reason") or "").strip().upper()
        if trace_degrade_reason == "EXECUTION_ERROR":
            diagnostics.recovery_reason = "EXECUTION_ERROR_NO_RECOVERY"
            return CandidateGenerationOutcome(
                accepted_candidates=[],
                recovery_candidates=[],
                diagnostics=diagnostics,
            )
        # Classify blocked shape to determine recovery reason
        blocked_shape = classify_blocked_shape(original_sql, sql_unit)
        diagnostics.recovery_reason = blocked_shape

    recovery_candidates = _recover_candidates(
        context,
        degraded_kind,
        raw_candidates,
        accepted_candidates,
    )

    if recovery_candidates:
        # If we had low-value candidates that were replaced by recovery, use different reason
        if degraded_kind == "ONLY_LOW_VALUE_CANDIDATES":
            diagnostics.recovery_reason = "SAFE_BASELINE_REPLACED_LOW_VALUE"
        else:
            diagnostics.recovery_reason = "SAFE_BASELINE_SHAPE_RECOVERY"
        # Use the specific recovery strategy from the first recovered candidate
        first_recovery = recovery_candidates[0] if recovery_candidates else {}
        diagnostics.recovery_strategy = str(first_recovery.get("rewriteStrategy") or "SHAPE_RECOVERY")
        diagnostics.recovered_candidate_count = len(recovery_candidates)

    return CandidateGenerationOutcome(
        accepted_candidates=accepted_candidates,
        recovery_candidates=recovery_candidates,
        diagnostics=diagnostics,
    )
