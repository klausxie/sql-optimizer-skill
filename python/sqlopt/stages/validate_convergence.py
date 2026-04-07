from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from ..platforms.sql.canonicalization_support import (
    DISTINCT_WRAPPER_RE,
    GROUP_BY_WRAPPER_RE,
    HAVING_WRAPPER_RE,
    SELECT_DIRECT_RE,
    cleanup_redundant_select_aliases,
    cleanup_single_table_alias_references,
    normalize_sql,
)
from ..utils import statement_key

TARGET_SHAPE_FAMILY = "IF_GUARDED_FILTER_STATEMENT"
STATIC_INCLUDE_SHAPE_FAMILY = "STATIC_INCLUDE_ONLY"
STATIC_STATEMENT_SHAPE_FAMILY = "STATIC_STATEMENT"
STATIC_SUBQUERY_WRAPPER_SHAPE_FAMILY = "STATIC_SUBQUERY_WRAPPER"
STATIC_ALIAS_PROJECTION_SHAPE_FAMILY = "STATIC_ALIAS_PROJECTION"
DISTINCT_WRAPPER_SHAPE_FAMILY = "DISTINCT_WRAPPER"
DISTINCT_ALIAS_SHAPE_FAMILY = "DISTINCT_ALIAS"
ORDER_BY_CONSTANT_SHAPE_FAMILY = "ORDER_BY_CONSTANT"
BOOLEAN_TAUTOLOGY_SHAPE_FAMILY = "BOOLEAN_TAUTOLOGY"
IN_LIST_SINGLE_VALUE_SHAPE_FAMILY = "IN_LIST_SINGLE_VALUE"
OR_SAME_COLUMN_SHAPE_FAMILY = "OR_SAME_COLUMN"
CASE_WHEN_TRUE_SHAPE_FAMILY = "CASE_WHEN_TRUE"
COALESCE_IDENTITY_SHAPE_FAMILY = "COALESCE_IDENTITY"
EXPRESSION_FOLDING_SHAPE_FAMILY = "EXPRESSION_FOLDING"
LIMIT_LARGE_SHAPE_FAMILY = "LIMIT_LARGE"
NULL_COMPARISON_SHAPE_FAMILY = "NULL_COMPARISON"
DISTINCT_ON_SHAPE_FAMILY = "DISTINCT_ON"
EXISTS_SELF_SHAPE_FAMILY = "EXISTS_SELF"
UNION_WRAPPER_SHAPE_FAMILY = "UNION_WRAPPER"
GROUP_BY_ALIAS_SHAPE_FAMILY = "GROUP_BY_ALIAS"
GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY = "GROUP_BY_HAVING_ALIAS"
GROUP_BY_WRAPPER_SHAPE_FAMILY = "GROUP_BY_WRAPPER"
HAVING_WRAPPER_SHAPE_FAMILY = "HAVING_WRAPPER"
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
DYNAMIC_COUNT_WRAPPER_TEMPLATE_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
STATIC_SUBQUERY_WRAPPER_TEMPLATE_RE = re.compile(
    r"^\s*select\s+.+?\s+from\s*\(\s*select\s+.+?\s+from\b.+?\)\s*[a-z_][a-z0-9_]*?(?:\s+(?:where\b|order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
RECOVERED_PATCH_FAMILY_BY_STRATEGY = {
    "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED": "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    "REMOVE_REDUNDANT_ALIASES": "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    "REMOVE_UNNECESSARY_ALIASES": "DYNAMIC_FILTER_SELECT_LIST_CLEANUP",
    "REMOVE_REDUNDANT_FROM_ALIAS_RECOVERED": "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP",
    "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED": "GROUP_BY_FROM_ALIAS_CLEANUP",
    "REMOVE_REDUNDANT_GROUP_BY_HAVING_FROM_ALIAS_RECOVERED": "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP",
    "REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED": "DISTINCT_FROM_ALIAS_CLEANUP",
    "REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED": "REDUNDANT_DISTINCT_WRAPPER",
    "REMOVE_CONSTANT_ORDER_BY_RECOVERED": "STATIC_ORDER_BY_SIMPLIFICATION",
    "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED": "STATIC_BOOLEAN_SIMPLIFICATION",
    "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED": "STATIC_IN_LIST_SIMPLIFICATION",
    "SIMPLIFY_OR_TO_IN_RECOVERED": "STATIC_OR_SIMPLIFICATION",
    "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED": "STATIC_CASE_SIMPLIFICATION",
    "SIMPLIFY_COALESCE_IDENTITY_RECOVERED": "STATIC_COALESCE_SIMPLIFICATION",
    "FOLD_CONSTANT_EXPRESSION_RECOVERED": "STATIC_EXPRESSION_FOLDING",
    "REMOVE_LARGE_LIMIT_RECOVERED": "STATIC_LIMIT_OPTIMIZATION",
    "SIMPLIFY_NULL_COMPARISON_RECOVERED": "STATIC_NULL_COMPARISON",
    "SIMPLIFY_DISTINCT_ON_RECOVERED": "STATIC_DISTINCT_ON_SIMPLIFICATION",
    "REMOVE_REDUNDANT_HAVING_WRAPPER_RECOVERED": "REDUNDANT_HAVING_WRAPPER",
    "REMOVE_REDUNDANT_SUBQUERY": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
    "REMOVE_REDUNDANT_SUBQUERY_RECOVERED": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
    "REMOVE_REDUNDANT_SUBQUERY_WRAPPER": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
    "INLINE_SUBQUERY": "DYNAMIC_FILTER_WRAPPER_COLLAPSE",
}
COUNT_WRAPPER_PATCH_FAMILY = "DYNAMIC_COUNT_WRAPPER_COLLAPSE"
STATIC_INCLUDE_PATCH_FAMILY = "STATIC_INCLUDE_WRAPPER_COLLAPSE"
STATIC_STATEMENT_PATCH_FAMILY = "STATIC_STATEMENT_REWRITE"
STATIC_CTE_PATCH_FAMILY = "STATIC_CTE_INLINE"
STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY = "STATIC_SUBQUERY_WRAPPER_COLLAPSE"
STATIC_ALIAS_PROJECTION_PATCH_FAMILY = "STATIC_ALIAS_PROJECTION_CLEANUP"
GROUP_BY_WRAPPER_PATCH_FAMILY = "REDUNDANT_GROUP_BY_WRAPPER"
HAVING_WRAPPER_PATCH_FAMILY = "REDUNDANT_HAVING_WRAPPER"
SUPPORTED_STATIC_SHAPE_FAMILIES = {
    STATIC_INCLUDE_SHAPE_FAMILY,
    STATIC_STATEMENT_SHAPE_FAMILY,
    STATIC_SUBQUERY_WRAPPER_SHAPE_FAMILY,
    STATIC_ALIAS_PROJECTION_SHAPE_FAMILY,
    DISTINCT_WRAPPER_SHAPE_FAMILY,
    DISTINCT_ALIAS_SHAPE_FAMILY,
    ORDER_BY_CONSTANT_SHAPE_FAMILY,
    BOOLEAN_TAUTOLOGY_SHAPE_FAMILY,
    IN_LIST_SINGLE_VALUE_SHAPE_FAMILY,
    OR_SAME_COLUMN_SHAPE_FAMILY,
    CASE_WHEN_TRUE_SHAPE_FAMILY,
    COALESCE_IDENTITY_SHAPE_FAMILY,
    EXPRESSION_FOLDING_SHAPE_FAMILY,
    LIMIT_LARGE_SHAPE_FAMILY,
    NULL_COMPARISON_SHAPE_FAMILY,
    DISTINCT_ON_SHAPE_FAMILY,
    EXISTS_SELF_SHAPE_FAMILY,
    UNION_WRAPPER_SHAPE_FAMILY,
    GROUP_BY_ALIAS_SHAPE_FAMILY,
    GROUP_BY_WRAPPER_SHAPE_FAMILY,
    HAVING_WRAPPER_SHAPE_FAMILY,
    GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY,
}
SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES: dict[tuple[str, str], str] = {
    ("IF_GUARDED_COUNT_WRAPPER", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): COUNT_WRAPPER_PATCH_FAMILY,
    (STATIC_INCLUDE_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): STATIC_INCLUDE_PATCH_FAMILY,
    (STATIC_SUBQUERY_WRAPPER_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
    (GROUP_BY_WRAPPER_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): GROUP_BY_WRAPPER_PATCH_FAMILY,
    (HAVING_WRAPPER_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): HAVING_WRAPPER_PATCH_FAMILY,
    (STATIC_ALIAS_PROJECTION_SHAPE_FAMILY, "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"): STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
    (DISTINCT_WRAPPER_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): "REDUNDANT_DISTINCT_WRAPPER",
    (GROUP_BY_ALIAS_SHAPE_FAMILY, "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"): "GROUP_BY_FROM_ALIAS_CLEANUP",
    (EXISTS_SELF_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): "STATIC_EXISTS_REWRITE",
    (UNION_WRAPPER_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): "STATIC_UNION_COLLAPSE",
    (STATIC_STATEMENT_SHAPE_FAMILY, "DYNAMIC_FILTER_WRAPPER_COLLAPSE"): STATIC_STATEMENT_PATCH_FAMILY,
    (STATIC_STATEMENT_SHAPE_FAMILY, "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"): STATIC_STATEMENT_PATCH_FAMILY,
    (STATIC_STATEMENT_SHAPE_FAMILY, "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"): STATIC_STATEMENT_PATCH_FAMILY,
}
SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES: dict[str, dict[str, str]] = {
    "IF_GUARDED_COUNT_WRAPPER": {
        "STRUCTURE_SIMPLIFICATION": COUNT_WRAPPER_PATCH_FAMILY,
        "SUBQUERY_REMOVAL": COUNT_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY": COUNT_WRAPPER_PATCH_FAMILY,
    },
    DISTINCT_WRAPPER_SHAPE_FAMILY: {
        "REMOVE_REDUNDANT_DISTINCT_WRAPPER_RECOVERED": "REDUNDANT_DISTINCT_WRAPPER",
    },
    DISTINCT_ALIAS_SHAPE_FAMILY: {
        "REMOVE_REDUNDANT_DISTINCT_FROM_ALIAS_RECOVERED": "DISTINCT_FROM_ALIAS_CLEANUP",
        "DISTINCT_FROM_ALIAS": "DISTINCT_FROM_ALIAS_CLEANUP",
    },
    ORDER_BY_CONSTANT_SHAPE_FAMILY: {
        "REMOVE_CONSTANT_ORDER_BY_RECOVERED": "STATIC_ORDER_BY_SIMPLIFICATION",
        "ORDER_BY_REWRITE": "STATIC_ORDER_BY_SIMPLIFICATION",
        "SORT": "STATIC_ORDER_BY_SIMPLIFICATION",
    },
    BOOLEAN_TAUTOLOGY_SHAPE_FAMILY: {
        "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED": "STATIC_BOOLEAN_SIMPLIFICATION",
        "REMOVE_TAUTOLOGY": "STATIC_BOOLEAN_SIMPLIFICATION",
    },
    IN_LIST_SINGLE_VALUE_SHAPE_FAMILY: {
        "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED": "STATIC_IN_LIST_SIMPLIFICATION",
        "SIMPLIFY_SINGLE_VALUE_IN_CLAUSE": "STATIC_IN_LIST_SIMPLIFICATION",
    },
    OR_SAME_COLUMN_SHAPE_FAMILY: {
        "SIMPLIFY_OR_TO_IN_RECOVERED": "STATIC_OR_SIMPLIFICATION",
        "OR_TO_IN": "STATIC_OR_SIMPLIFICATION",
    },
    CASE_WHEN_TRUE_SHAPE_FAMILY: {
        "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED": "STATIC_CASE_SIMPLIFICATION",
        "CASE_SIMPLIFICATION": "STATIC_CASE_SIMPLIFICATION",
    },
    COALESCE_IDENTITY_SHAPE_FAMILY: {
        "SIMPLIFY_COALESCE_IDENTITY_RECOVERED": "STATIC_COALESCE_SIMPLIFICATION",
        "COALESCE_SIMPLIFICATION": "STATIC_COALESCE_SIMPLIFICATION",
    },
    EXPRESSION_FOLDING_SHAPE_FAMILY: {
        "FOLD_CONSTANT_EXPRESSION_RECOVERED": "STATIC_EXPRESSION_FOLDING",
        "EXPRESSION_FOLDING": "STATIC_EXPRESSION_FOLDING",
    },
    LIMIT_LARGE_SHAPE_FAMILY: {
        "REMOVE_LARGE_LIMIT_RECOVERED": "STATIC_LIMIT_OPTIMIZATION",
        "REMOVE_INVALID_LIMIT": "STATIC_LIMIT_OPTIMIZATION",
    },
    NULL_COMPARISON_SHAPE_FAMILY: {
        "SIMPLIFY_NULL_COMPARISON_RECOVERED": "STATIC_NULL_COMPARISON",
        "NULL_COMPARISON_FIX": "STATIC_NULL_COMPARISON",
        "NULL_COMPARISON": "STATIC_NULL_COMPARISON",
    },
    DISTINCT_ON_SHAPE_FAMILY: {
        "SIMPLIFY_DISTINCT_ON_RECOVERED": "STATIC_DISTINCT_ON_SIMPLIFICATION",
        "SEMANTIC_PRESERVING": "STATIC_DISTINCT_ON_SIMPLIFICATION",
        "SAFE_DISTINCT_ON_SIMPLIFICATION": "STATIC_DISTINCT_ON_SIMPLIFICATION",
    },
    EXISTS_SELF_SHAPE_FAMILY: {
        "SAFE_EXISTS_REWRITE": "STATIC_EXISTS_REWRITE",
        "REDUNDANT_SUBQUERY_REMOVAL": "STATIC_EXISTS_REWRITE",
        "REMOVE_REDUNDANT_EXISTS": "STATIC_EXISTS_REWRITE",
    },
    UNION_WRAPPER_SHAPE_FAMILY: {
        "SAFE_UNION_COLLAPSE": "STATIC_UNION_COLLAPSE",
        "REMOVE_REDUNDANT_SUBQUERY_WRAPPER": "STATIC_UNION_COLLAPSE",
    },
    STATIC_INCLUDE_SHAPE_FAMILY: {
        "INLINE_SUBQUERY": STATIC_INCLUDE_PATCH_FAMILY,
        "SUBQUERY_REMOVAL": STATIC_INCLUDE_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY": STATIC_INCLUDE_PATCH_FAMILY,
    },
    STATIC_SUBQUERY_WRAPPER_SHAPE_FAMILY: {
        "INLINE_SUBQUERY": STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
        "SUBQUERY_REMOVAL": STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY": STATIC_SUBQUERY_WRAPPER_PATCH_FAMILY,
    },
    GROUP_BY_WRAPPER_SHAPE_FAMILY: {
        "INLINE_SUBQUERY": GROUP_BY_WRAPPER_PATCH_FAMILY,
        "SUBQUERY_REMOVAL": GROUP_BY_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY": GROUP_BY_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY_RECOVERED": GROUP_BY_WRAPPER_PATCH_FAMILY,
    },
    HAVING_WRAPPER_SHAPE_FAMILY: {
        "INLINE_SUBQUERY": HAVING_WRAPPER_PATCH_FAMILY,
        "SUBQUERY_REMOVAL": HAVING_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY": HAVING_WRAPPER_PATCH_FAMILY,
        "REMOVE_REDUNDANT_SUBQUERY_RECOVERED": HAVING_WRAPPER_PATCH_FAMILY,
    },
    STATIC_ALIAS_PROJECTION_SHAPE_FAMILY: {
        "REMOVE_REDUNDANT_SELECT_ALIAS_RECOVERED": STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
        "REMOVE_REDUNDANT_ALIASES": STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
        "REMOVE_UNNECESSARY_ALIASES": STATIC_ALIAS_PROJECTION_PATCH_FAMILY,
    },
    GROUP_BY_ALIAS_SHAPE_FAMILY: {
        "REMOVE_REDUNDANT_GROUP_BY_FROM_ALIAS_RECOVERED": "GROUP_BY_FROM_ALIAS_CLEANUP",
        "GROUP_BY_FROM_ALIAS": "GROUP_BY_FROM_ALIAS_CLEANUP",
    },
    STATIC_STATEMENT_SHAPE_FAMILY: {
        "REMOVE_REDUNDANT_SUBQUERY": STATIC_STATEMENT_PATCH_FAMILY,
        "INLINE_SUBQUERY": STATIC_STATEMENT_PATCH_FAMILY,
        "INLINE_CTE": STATIC_CTE_PATCH_FAMILY,
        "CTE_INLINE": STATIC_CTE_PATCH_FAMILY,
    },
}


def normalize_strategy_name(value: str) -> str:
    return NON_ALNUM_RE.sub("_", str(value or "").strip().upper()).strip("_")


def patch_family_from_strategy_name(value: str) -> str | None:
    strategy = normalize_strategy_name(value)
    if strategy in RECOVERED_PATCH_FAMILY_BY_STRATEGY:
        return RECOVERED_PATCH_FAMILY_BY_STRATEGY[strategy]

    heuristic_cases = (
        ("SIMPLIFY_ALIASES", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("REDUNDANT_SELECT_ALIAS", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("REDUNDANT_ALIASES", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("REDUNDANT_ALIAS_REMOVAL", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("ALIAS_REMOVAL", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("UNNECESSARY_ALIASES", "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"),
        ("REDUNDANT_FROM_ALIAS", "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"),
        ("GROUP_BY_HAVING_FROM_ALIAS", "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"),
        ("GROUP_BY_FROM_ALIAS", "GROUP_BY_FROM_ALIAS_CLEANUP"),
        ("DISTINCT_FROM_ALIAS", "DISTINCT_FROM_ALIAS_CLEANUP"),
        ("SINGLE_VALUE_IN_LIST", "STATIC_IN_LIST_SIMPLIFICATION"),
        ("SINGLE_VALUE_IN_CLAUSE", "STATIC_IN_LIST_SIMPLIFICATION"),
        ("REMOVE_TAUTOLOGY", "STATIC_BOOLEAN_SIMPLIFICATION"),
        ("IN_LIST_SIMPLIFICATION", "STATIC_IN_LIST_SIMPLIFICATION"),
        ("OR_TO_IN", "STATIC_OR_SIMPLIFICATION"),
        ("CASE_SIMPLIFICATION", "STATIC_CASE_SIMPLIFICATION"),
        ("NOOP_CASE", "STATIC_CASE_SIMPLIFICATION"),
        ("REDUNDANT_CASE", "STATIC_CASE_SIMPLIFICATION"),
        ("COALESCE_SIMPLIFICATION", "STATIC_COALESCE_SIMPLIFICATION"),
        ("EXPRESSION_FOLDING", "STATIC_EXPRESSION_FOLDING"),
        ("CONSTANT_FOLDING", "STATIC_EXPRESSION_FOLDING"),
        ("FOLDED_EXPRESSION", "STATIC_EXPRESSION_FOLDING"),
        ("SIMPLIFY_EXPRESSION", "STATIC_EXPRESSION_FOLDING"),
        ("LARGE_LIMIT", "STATIC_LIMIT_OPTIMIZATION"),
        ("NULL_COMPARISON", "STATIC_NULL_COMPARISON"),
        ("DISTINCT_ON", "STATIC_DISTINCT_ON_SIMPLIFICATION"),
        ("MEANINGLESS_ORDER_BY", "STATIC_ORDER_BY_SIMPLIFICATION"),
        ("INVALID_ORDER_BY", "STATIC_ORDER_BY_SIMPLIFICATION"),
        ("SAFE_EXISTS_REWRITE", "STATIC_EXISTS_REWRITE"),
        ("SAFE_UNION_COLLAPSE", "STATIC_UNION_COLLAPSE"),
        ("INLINE_CTE", STATIC_CTE_PATCH_FAMILY),
        ("CTE_INLINE", STATIC_CTE_PATCH_FAMILY),
        ("SUBQUERY_REMOVAL", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
        ("SUBQUERY_UNWRAP", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
        ("REDUNDANT_SUBQUERY", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
        ("SUBQUERY_WRAPPER", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
        ("INLINE_SUBQUERY", "DYNAMIC_FILTER_WRAPPER_COLLAPSE"),
    )
    for marker, family in heuristic_cases:
        if marker in strategy:
            return family
    return None


def normalize_patch_family_for_shape(shape_family: str, family: str | None) -> str | None:
    normalized_shape = str(shape_family or "").strip().upper()
    normalized_family = str(family or "").strip()
    if not normalized_family:
        return None
    return SHAPE_NORMALIZED_PATCH_FAMILY_OVERRIDES.get((normalized_shape, normalized_family), normalized_family)


def shape_specific_patch_family_hint(
    shape_family: str,
    proposal: dict[str, Any],
    selected_candidate_ids: set[str] | None = None,
) -> str | None:
    normalized_shape = str(shape_family or "").strip().upper()
    strategy_family_map = SHAPE_SPECIFIC_STRATEGY_PATCH_FAMILIES.get(normalized_shape, {})
    llm_candidates = proposal.get("llmCandidates") or []
    if not isinstance(llm_candidates, list):
        return None
    selected_ids = {str(value).strip() for value in (selected_candidate_ids or set()) if str(value).strip()}
    for candidate in llm_candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("id") or "").strip()
        if selected_ids and candidate_id not in selected_ids:
            continue
        strategy = normalize_strategy_name(str(candidate.get("rewriteStrategy") or ""))
        family = strategy_family_map.get(strategy)
        if family:
            return family
    return None


def dynamic_template_profile(row: dict[str, Any]) -> dict[str, Any]:
    rewrite_facts = row.get("rewriteFacts") or {}
    dynamic_template = (rewrite_facts.get("dynamicTemplate") or {}) if isinstance(rewrite_facts, dict) else {}
    profile = (dynamic_template.get("capabilityProfile") or {}) if isinstance(dynamic_template, dict) else {}
    return profile if isinstance(profile, dict) else {}


def shape_family_for_row(row: dict[str, Any]) -> str:
    profile = dynamic_template_profile(row)
    return str(profile.get("shapeFamily") or "").strip().upper()


def patch_family_for_row(row: dict[str, Any]) -> str | None:
    profile = dynamic_template_profile(row)
    value = str(profile.get("baselineFamily") or "").strip()
    return value or None


def patch_surface_for_row(row: dict[str, Any]) -> str | None:
    profile = dynamic_template_profile(row)
    value = str(profile.get("patchSurface") or "").strip()
    return value or None


def rewrite_ops_fingerprint(row: dict[str, Any]) -> str | None:
    ops = row.get("templateRewriteOps") or []
    if not isinstance(ops, list):
        return None
    tokens: list[str] = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_name = str(op.get("op") or "").strip()
        if not op_name:
            continue
        target_ref = str(op.get("targetRef") or "").strip()
        tokens.append(f"{op_name}:{target_ref}")
    if not tokens:
        return None
    return "|".join(sorted(tokens))


def semantic_gate_status(row: dict[str, Any]) -> str:
    semantic = row.get("semanticEquivalence") or {}
    if not isinstance(semantic, dict):
        return "UNCERTAIN"
    return str(semantic.get("status") or "UNCERTAIN").strip().upper() or "UNCERTAIN"


def selected_candidate_id(row: dict[str, Any]) -> str | None:
    value = str(row.get("selectedCandidateId") or "").strip()
    return value or None


def statement_key_for_row(row: dict[str, Any]) -> str:
    sql_key = str(row.get("sqlKey") or "")
    explicit_statement_key = str(row.get("statementKey") or "")
    return statement_key(sql_key, explicit_statement_key)


def infer_shape_family_from_sql_unit(sql_unit: dict[str, Any]) -> str:
    dynamic_features = {str(item).strip().upper() for item in (sql_unit.get("dynamicFeatures") or []) if str(item).strip()}
    raw_template_sql = str(sql_unit.get("templateSql") or "")
    template_sql = raw_template_sql.lower()
    statement_sql = str(sql_unit.get("sql") or "").strip().upper()
    normalized_sql = normalize_sql(raw_template_sql)
    within_where = "WHERE" in dynamic_features or "<where" in template_sql
    conditional_filter = "IF" in dynamic_features or "<if" in template_sql
    choose_filter = "CHOOSE" in dynamic_features or "<choose" in template_sql
    if within_where and (conditional_filter or choose_filter):
        if (statement_sql.startswith("SELECT COUNT(") or "COUNT(" in statement_sql) and DYNAMIC_COUNT_WRAPPER_TEMPLATE_RE.match(raw_template_sql.strip()):
            return "IF_GUARDED_COUNT_WRAPPER"
        return "IF_GUARDED_FILTER_STATEMENT"
    if not dynamic_features and "OVER(" in statement_sql.replace(" ", ""):
        return "WINDOW"
    if not dynamic_features and re.search(r"\bORDER\s+BY\s+(NULL|\d+|'[^']*'|\"[^\"]*\"|[\d\.]+)\s*$", normalized_sql, flags=re.IGNORECASE):
        return ORDER_BY_CONSTANT_SHAPE_FAMILY
    if not dynamic_features and re.search(r"\bWHERE\s+(1\s*=\s*1|0\s*=\s*0|TRUE)\b", normalized_sql, flags=re.IGNORECASE):
        return BOOLEAN_TAUTOLOGY_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\bWHERE\b.+\b(?:NOT\s+)?IN\s*\(\s*[^,\)]+\s*\)",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return IN_LIST_SINGLE_VALUE_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\b[a-z_][a-z0-9_\.]*\s*=\s*('[^']*'|[^'\s\)]+)\s+OR\s+[a-z_][a-z0-9_\.]*\s*=\s*('[^']*'|[^'\s\)]+)",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return OR_SAME_COLUMN_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\bCASE\s+WHEN\s+TRUE\s+THEN\s+.+?\s+ELSE\s+.+?\s+END\b",
        normalized_sql,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        return CASE_WHEN_TRUE_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\bCOALESCE\s*\(\s*[a-z_][a-z0-9_\.]*\s*,\s*([a-z_][a-z0-9_\.]*|NULL)\s*\)",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return COALESCE_IDENTITY_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\b\d+\s*[+\-*/]\s*\d+\b",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return EXPRESSION_FOLDING_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\blimit\s+\d+\s*$",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        limit_match = re.search(r"\blimit\s+(?P<value>\d+)\s*$", normalized_sql, flags=re.IGNORECASE)
        if limit_match is not None:
            try:
                if int(limit_match.group("value")) >= 1000000:
                    return LIMIT_LARGE_SHAPE_FAMILY
            except ValueError:
                pass
    if not dynamic_features and re.search(
        r"\b[a-z_][a-z0-9_\.]*\s*(=|!=|<>)\s*null\b",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return NULL_COMPARISON_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\bselect\s+distinct\s+on\s*\(",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return DISTINCT_ON_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"\bwhere\s+exists\s*\(\s*select\s+1\s+from\s+[a-z_][a-z0-9_]*\s+[a-z_][a-z0-9_]*\s+where\s+[a-z_][a-z0-9_]*\.id\s*=\s*[a-z_][a-z0-9_]*\.id\s*\)",
        normalized_sql,
        flags=re.IGNORECASE,
    ):
        return EXISTS_SELF_SHAPE_FAMILY
    if not dynamic_features and re.search(
        r"^\s*select\s+.+?\s+from\s*\(\s*select\b.+\bunion(?:\s+all)?\b.+\)\s*[a-z_][a-z0-9_]*",
        normalized_sql,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        return UNION_WRAPPER_SHAPE_FAMILY
    if not dynamic_features and "UNION" in statement_sql:
        return "UNION"
    if not dynamic_features and statement_sql.startswith("SELECT DISTINCT "):
        if DISTINCT_WRAPPER_RE.match(normalized_sql):
            return DISTINCT_WRAPPER_SHAPE_FAMILY
    if not dynamic_features:
        having_wrapper_match = HAVING_WRAPPER_RE.match(normalized_sql)
        if having_wrapper_match is not None:
            inner_from = normalize_sql(str(having_wrapper_match.group("inner_from") or ""))
            inner_from_upper = f" {inner_from.upper()} "
            if " HAVING " in inner_from_upper:
                return HAVING_WRAPPER_SHAPE_FAMILY
    if not dynamic_features:
        group_by_wrapper_match = GROUP_BY_WRAPPER_RE.match(normalized_sql)
        if group_by_wrapper_match is not None:
            inner_from = normalize_sql(str(group_by_wrapper_match.group("inner_from") or ""))
            inner_from_upper = f" {inner_from.upper()} "
            if " GROUP BY " in inner_from_upper and " HAVING " not in inner_from_upper:
                return GROUP_BY_WRAPPER_SHAPE_FAMILY
    if not dynamic_features and STATIC_SUBQUERY_WRAPPER_TEMPLATE_RE.match(normalized_sql):
        return STATIC_SUBQUERY_WRAPPER_SHAPE_FAMILY
    if not dynamic_features:
        direct_match = SELECT_DIRECT_RE.match(normalized_sql)
        if direct_match is not None:
            original_select = str(direct_match.group("select") or "")
            original_from = str(direct_match.group("from") or "")
            cleaned_select_refs, cleaned_from_refs, alias_refs_changed = cleanup_single_table_alias_references(
                original_select,
                original_from,
            )
            if alias_refs_changed:
                from_upper = f" {normalize_sql(cleaned_from_refs).upper()} "
                if normalize_sql(cleaned_select_refs).upper().startswith("DISTINCT "):
                    return DISTINCT_ALIAS_SHAPE_FAMILY
                if " GROUP BY " in from_upper and " HAVING " not in from_upper:
                    return GROUP_BY_ALIAS_SHAPE_FAMILY
                if " GROUP BY " in from_upper and " HAVING " in from_upper:
                    return GROUP_BY_HAVING_ALIAS_SHAPE_FAMILY
            cleaned_select, aliases_changed = cleanup_redundant_select_aliases(str(direct_match.group("select") or ""))
            if aliases_changed and normalize_sql(cleaned_select) != normalize_sql(str(direct_match.group("select") or "")):
                return STATIC_ALIAS_PROJECTION_SHAPE_FAMILY
    if dynamic_features and dynamic_features <= {"INCLUDE"} and "<include" in template_sql:
        return STATIC_INCLUDE_SHAPE_FAMILY
    if not dynamic_features:
        return STATIC_STATEMENT_SHAPE_FAMILY
    return "UNKNOWN"


def target_shape_supported(sql_unit: dict[str, Any], shape_family: str, patch_families: set[str] | None = None) -> bool:
    if shape_family == "IF_GUARDED_COUNT_WRAPPER":
        normalized_patch_families = {str(value or "").strip().upper() for value in (patch_families or set()) if str(value).strip()}
        return normalized_patch_families == {COUNT_WRAPPER_PATCH_FAMILY}
    if shape_family in SUPPORTED_STATIC_SHAPE_FAMILIES:
        return True
    if shape_family == "UNION":
        return False
    if shape_family != TARGET_SHAPE_FAMILY:
        return False
    dynamic_features = {str(item).strip().upper() for item in (sql_unit.get("dynamicFeatures") or []) if str(item).strip()}
    template_sql = str(sql_unit.get("templateSql") or "").lower()
    if "CHOOSE" in dynamic_features or "<choose" in template_sql:
        normalized_patch_families = {str(value or "").strip().upper() for value in (patch_families or set()) if str(value).strip()}
        return normalized_patch_families == {"DYNAMIC_FILTER_SELECT_LIST_CLEANUP"}
    return True


def proposal_patch_family_hint(proposal: dict[str, Any], selected_candidate_ids: set[str] | None = None) -> str | None:
    diagnostics = proposal.get("candidateGenerationDiagnostics") or {}
    family = patch_family_from_strategy_name(str(diagnostics.get("recoveryStrategy") or ""))
    if family:
        return family

    llm_candidates = proposal.get("llmCandidates") or []
    if isinstance(llm_candidates, list):
        selected_ids = {str(value).strip() for value in (selected_candidate_ids or set()) if str(value).strip()}
        if selected_ids:
            for candidate in llm_candidates:
                if not isinstance(candidate, dict):
                    continue
                candidate_id = str(candidate.get("id") or "").strip()
                if candidate_id not in selected_ids:
                    continue
                family = patch_family_from_strategy_name(str(candidate.get("rewriteStrategy") or ""))
                if family:
                    return family
        if len(llm_candidates) == 1:
            family = patch_family_from_strategy_name(str(((llm_candidates[0] or {}).get("rewriteStrategy") or "")))
            if family:
                return family
    return None


def build_statement_convergence_row(
    *,
    statement_key_value: str,
    rows: list[dict[str, Any]],
    sql_key: str,
    acceptance_path: Path,
    sql_index_path: Path,
    sql_unit: dict[str, Any],
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_counts = {"pass": 0, "partial": 0, "fail": 0}
    semantic_counts = {"passCount": 0, "blockedCount": 0, "uncertainCount": 0}
    shape_families = [
        shape
        for shape in (shape_family_for_row(row) for row in rows)
        if shape and shape not in {"UNKNOWN", "NONE"}
    ]
    shape_family = shape_families[0] if shape_families else infer_shape_family_from_sql_unit(sql_unit)
    sql_keys = sorted({str(row.get("sqlKey") or "").strip() for row in rows if str(row.get("sqlKey") or "").strip()})
    patch_families = {family for family in (patch_family_for_row(row) for row in rows) if family}
    selected_candidate_ids = {candidate_id for candidate_id in (selected_candidate_id(row) for row in rows) if candidate_id}
    family_hint = proposal_patch_family_hint(proposal or {}, selected_candidate_ids)
    if not family_hint:
        family_hint = shape_specific_patch_family_hint(shape_family, proposal or {}, selected_candidate_ids)
    if not patch_families and family_hint:
        patch_families = {family_hint}
    patch_families = {
        normalized_family
        for normalized_family in (
            normalize_patch_family_for_shape(shape_family, family)
            for family in patch_families
        )
        if normalized_family
    }
    patch_surfaces = {surface for surface in (patch_surface_for_row(row) for row in rows) if surface}
    rewrite_ops_fingerprints = {fingerprint for fingerprint in (rewrite_ops_fingerprint(row) for row in rows) if fingerprint}

    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if status == "PASS":
            status_counts["pass"] += 1
        elif status in {"FAIL", "FAILED"}:
            status_counts["fail"] += 1
        else:
            status_counts["partial"] += 1

        gate = semantic_gate_status(row)
        if gate == "PASS":
            semantic_counts["passCount"] += 1
        elif gate == "BLOCKED":
            semantic_counts["blockedCount"] += 1
        else:
            semantic_counts["uncertainCount"] += 1

    decision = "AUTO_PATCHABLE"
    conflict_reason: str | None = None
    consensus: dict[str, Any] | None = None

    if not target_shape_supported(sql_unit, shape_family, patch_families):
        decision = "MANUAL_REVIEW"
        conflict_reason = "SHAPE_FAMILY_NOT_TARGET"
    elif status_counts["partial"] > 0 or status_counts["fail"] > 0:
        decision = "MANUAL_REVIEW"
        conflict_reason = "VALIDATE_STATUS_NOT_PASS"
    elif semantic_counts["blockedCount"] > 0 or semantic_counts["uncertainCount"] > 0:
        decision = "MANUAL_REVIEW"
        conflict_reason = "SEMANTIC_GATE_NOT_PASS"
    elif not selected_candidate_ids and not patch_families:
        decision = "MANUAL_REVIEW"
        conflict_reason = "NO_PATCHABLE_CANDIDATE_SELECTED"
    elif len(patch_families) != 1:
        decision = "MANUAL_REVIEW"
        conflict_reason = "PATCH_FAMILY_CONFLICT_OR_MISSING"
    elif len(patch_surfaces) > 1:
        decision = "MANUAL_REVIEW"
        conflict_reason = "PATCH_SURFACE_CONFLICT"
    elif len(rewrite_ops_fingerprints) > 1:
        decision = "MANUAL_REVIEW"
        conflict_reason = "REWRITE_OPS_CONFLICT"
    else:
        consensus = {
            "patchFamily": next(iter(patch_families), None),
            "patchSurface": next(iter(patch_surfaces), None),
            "rewriteOpsFingerprint": next(iter(rewrite_ops_fingerprints), None),
        }

    return {
        "statementKey": statement_key_value,
        "shapeFamily": shape_family,
        "coverageLevel": "representative",
        "sqlKeys": sql_keys,
        "validateStatuses": status_counts,
        "semanticGate": semantic_counts,
        "convergenceDecision": decision,
        "consensus": consensus,
        "conflictReason": conflict_reason,
        "evidenceRefs": [str(acceptance_path), str(sql_index_path)],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
