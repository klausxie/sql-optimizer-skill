"""Patch-related utility functions for patch_generate stage.

This module contains patch classification functions that were previously
in validator_sql.py. The separation ensures validate stage does not
depend on patch stage logic.
"""

from __future__ import annotations

import re
from typing import Any

from .canonicalization_support import SELECT_DIRECT_RE, cleanup_redundant_select_aliases, normalize_sql


# Regex patterns for patch classification
_SINGLE_TABLE_ALIAS_RE = re.compile(
    r"^\s*from\s+(?P<table>[a-z_][a-z0-9_\.]*)(?:\s+(?:as\s+)?(?P<alias>[a-z_][a-z0-9_]*))?(?P<suffix>.*)$",
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
_IN_SINGLE_VALUE_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s+IN\s*\(\s*([^,\)]+)\s*\)",
    flags=re.IGNORECASE,
)
_NOT_IN_SINGLE_VALUE_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s+NOT\s+IN\s*\(\s*([^,\)]+)\s*\)",
    flags=re.IGNORECASE,
)
_COLUMN_EQ_VALUE_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s*=\s*(.+)$",
    flags=re.IGNORECASE,
)
_COLUMN_NEQ_VALUE_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s*(<>|!=)\s*(.+)$",
    flags=re.IGNORECASE,
)
_LIMIT_ZERO_RE = re.compile(
    r"\bLIMIT\s+0\s*($|;|\))",
    flags=re.IGNORECASE,
)
_LIMIT_LARGE_RE = re.compile(
    r"\bLIMIT\s+(\d{10,}|\d{1,9}[0-9]{3,})\s*($|;|\))",
    flags=re.IGNORECASE,
)
_ORDER_BY_CONSTANT_RE = re.compile(
    r"\bORDER\s+BY\s+(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+)(\s*,\s*(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+))*($|;|\)|LIMIT)",
    flags=re.IGNORECASE,
)
_OR_SAME_COLUMN_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s*=\s*([^'\s]+|'[^']*')\s+OR\s+\1\s*=\s*\2",
    flags=re.IGNORECASE,
)
_DISTINCT_ON_RE = re.compile(
    r"\bSELECT\s+DISTINCT\s+ON\s*\([^)]+\)",
    flags=re.IGNORECASE,
)
_SUBQUERY_WRAPPER_RE = re.compile(
    r"\bFROM\s+\(\s*SELECT\s+[^)]+\s+FROM\s+",
    flags=re.IGNORECASE | re.DOTALL,
)
_BOOLEAN_CONSTANT_RE = re.compile(
    r"\b(1\s*=\s*1|0\s*=\s*0|1\s*<>?\s*1|0\s*<>?\s*0)\b",
    flags=re.IGNORECASE,
)
_CASE_SIMPLIFY_RE = re.compile(
    r"\bCASE\s+WHEN\s+TRUE\s+THEN\b",
    flags=re.IGNORECASE,
)
_COALESCE_SIMPLIFY_RE = re.compile(
    r"\bCOALESCE\s*\(\s*([a-z_][a-z0-9_\.]*)\s*,\s*(\1|NULL)\s*\)",
    flags=re.IGNORECASE,
)
_EXPRESSION_FOLDING_RE = re.compile(
    r"\b(\d+)\s*([+\-*/])\s*(\d+)\b",
    flags=re.IGNORECASE,
)
_NULL_COMPARISON_RE = re.compile(
    r"\b([a-z_][a-z0-9_\.]*)\s*(=|<>|!=)\s*NULL\b",
    flags=re.IGNORECASE,
)


def patch_template_settings(config: dict[str, Any] | None) -> dict[str, bool]:
    """Extract patch template settings from config."""
    patch_cfg = ((config or {}).get("patch", {}) if isinstance(config, dict) else {}) or {}
    template_cfg = (patch_cfg.get("template_rewrite", {}) if isinstance(patch_cfg, dict) else {}) or {}
    return {
        "enable_fragment_materialization": bool(template_cfg.get("enable_fragment_materialization", False)),
    }


def derive_patch_target_family(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    rewrite_facts: dict[str, Any] | None,
    rewrite_materialization: dict[str, Any] | None,
    selected_patch_strategy: dict[str, Any] | None,
    classify_patch_family: callable | None = None,
) -> str | None:
    """Derive the patch target family based on rewrite facts and strategy."""
    dynamic_profile = dict(((rewrite_facts or {}).get("dynamicTemplate") or {}).get("capabilityProfile") or {})
    dynamic_family = str(dynamic_profile.get("baselineFamily") or "").strip()
    if dynamic_family:
        return dynamic_family

    aggregation_profile = dict(((rewrite_facts or {}).get("aggregationQuery") or {}).get("capabilityProfile") or {})
    aggregation_family = str(aggregation_profile.get("safeBaselineFamily") or "").strip()
    if aggregation_family:
        return aggregation_family

    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type == "SAFE_WRAPPER_COLLAPSE":
        return "STATIC_WRAPPER_COLLAPSE"

    cte_query = dict((rewrite_facts or {}).get("cteQuery") or {})
    if cte_query.get("inlineCandidate"):
        return "STATIC_CTE_INLINE"

    if classify_patch_family is not None:
        from ..patch_families.classification import ClassificationContext
        ctx = ClassificationContext(
            original_sql=original_sql,
            rewritten_sql=rewritten_sql,
            rewrite_facts=rewrite_facts,
            selected_patch_strategy=selected_patch_strategy,
        )
        config_family = classify_patch_family(ctx)
        if config_family:
            return config_family

    alias_guarded, alias_family = classify_static_alias_projection_cleanup(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        selected_patch_strategy=selected_patch_strategy,
    )
    if alias_guarded:
        return alias_family

    if classify_static_in_list_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_IN_LIST_SIMPLIFICATION"

    if classify_static_limit_optimization(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_LIMIT_OPTIMIZATION"

    if classify_static_order_by_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_ORDER_BY_SIMPLIFICATION"

    if classify_static_or_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_OR_SIMPLIFICATION"

    if classify_static_distinct_on_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_DISTINCT_ON_SIMPLIFICATION"

    if classify_static_subquery_wrapper_collapse(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_SUBQUERY_WRAPPER_COLLAPSE"

    if classify_static_boolean_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_BOOLEAN_SIMPLIFICATION"

    if classify_static_case_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_CASE_SIMPLIFICATION"

    if classify_static_coalesce_simplification(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_COALESCE_SIMPLIFICATION"

    if classify_static_expression_folding(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_EXPRESSION_FOLDING"

    if classify_static_null_comparison(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        selected_patch_strategy=selected_patch_strategy,
    ):
        return "STATIC_NULL_COMPARISON"

    if strategy_type == "EXACT_TEMPLATE_EDIT":
        return "STATIC_STATEMENT_REWRITE"
    return None


def classify_static_alias_projection_cleanup(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    rewrite_facts: dict[str, Any] | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """Classify if the transformation is static alias projection cleanup."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False, None

    dynamic_template = dict((rewrite_facts or {}).get("dynamicTemplate") or {})
    aggregation_query = dict((rewrite_facts or {}).get("aggregationQuery") or {})
    cte_query = dict((rewrite_facts or {}).get("cteQuery") or {})
    if dynamic_template.get("present") or aggregation_query.get("present") or cte_query.get("present"):
        return False, None

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql or "")
    original_match = SELECT_DIRECT_RE.match(normalized_original)
    rewritten_match = SELECT_DIRECT_RE.match(normalized_rewritten)
    if original_match is None or rewritten_match is None:
        return False, None

    original_select = normalize_sql(original_match.group("select"))
    original_from = normalize_sql(original_match.group("from"))
    rewritten_select = normalize_sql(rewritten_match.group("select"))
    rewritten_from = normalize_sql(rewritten_match.group("from"))
    cleaned_select, aliases_changed = cleanup_redundant_select_aliases(original_select)
    if not aliases_changed:
        return False, None

    if uses_single_table_alias_qualifier(
        original_select=original_select,
        original_from=original_from,
        rewritten_select=rewritten_select,
        rewritten_from=rewritten_from,
    ):
        return True, None
    if rewritten_from != original_from:
        return True, None
    if normalize_sql(cleaned_select) != rewritten_select:
        return True, None
    return True, "STATIC_ALIAS_PROJECTION_CLEANUP"


def extract_single_table_alias(from_clause: str) -> str | None:
    """Extract single table alias from FROM clause."""
    match = _SINGLE_TABLE_ALIAS_RE.match(normalize_sql(from_clause))
    if match is None:
        return None
    alias = str(match.group("alias") or "").strip().lower()
    if not alias or alias in _FROM_ALIAS_RESERVED:
        return None
    return alias


def uses_single_table_alias_qualifier(
    *,
    original_select: str,
    original_from: str,
    rewritten_select: str,
    rewritten_from: str,
) -> bool:
    """Check if single table alias qualifier is used."""
    aliases = {
        alias
        for alias in (
            extract_single_table_alias(original_from),
            extract_single_table_alias(rewritten_from),
        )
        if alias
    }
    for alias in aliases:
        qualifier = f"{alias}."
        if any(
            qualifier in fragment.lower()
            for fragment in (original_select, original_from, rewritten_select, rewritten_from)
        ):
            return True
    return False


def classify_static_in_list_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if the transformation is IN(single) -> = or NOT IN(single) -> <>/!=."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    in_match = _IN_SINGLE_VALUE_RE.search(normalized_original)
    if in_match:
        column = in_match.group(1)
        in_value = in_match.group(2).strip()
        for line in normalized_rewritten.splitlines():
            eq_match = _COLUMN_EQ_VALUE_RE.search(line)
            if eq_match and eq_match.group(1) == column:
                rewritten_value = eq_match.group(2).strip()
                if rewritten_value == in_value:
                    return True

    not_in_match = _NOT_IN_SINGLE_VALUE_RE.search(normalized_original)
    if not_in_match:
        column = not_in_match.group(1)
        not_in_value = not_in_match.group(2).strip()
        for line in normalized_rewritten.splitlines():
            neq_match = _COLUMN_NEQ_VALUE_RE.search(line)
            if neq_match and neq_match.group(1) == column:
                rewritten_value = neq_match.group(3).strip()
                if rewritten_value == not_in_value:
                    return True

    return False


def classify_static_limit_optimization(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if the transformation removes useless LIMIT."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    limit_zero_match = _LIMIT_ZERO_RE.search(normalized_original)
    if limit_zero_match:
        if "LIMIT" not in normalized_rewritten.upper():
            return True
        if _LIMIT_ZERO_RE.search(normalized_rewritten):
            return True

    limit_large_match = _LIMIT_LARGE_RE.search(normalized_original)
    if limit_large_match:
        if "LIMIT" not in normalized_rewritten.upper():
            return True

    return False


def classify_static_order_by_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if the transformation removes useless ORDER BY."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    order_by_match = _ORDER_BY_CONSTANT_RE.search(normalized_original)
    if order_by_match:
        if "ORDER" not in normalized_rewritten.upper():
            return True

    return False


def classify_static_or_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if the transformation converts OR to IN for same column."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    or_match = _OR_SAME_COLUMN_RE.search(normalized_original)
    if or_match:
        column = or_match.group(1)
        in_pattern = re.compile(rf"\b{re.escape(column)}\s+IN\s*\(", flags=re.IGNORECASE)
        if in_pattern.search(normalized_rewritten):
            return True

    return False


def classify_static_distinct_on_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if DISTINCT ON is simplified or removed."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    distinct_on_match = _DISTINCT_ON_RE.search(normalized_original)
    if distinct_on_match:
        distinct_pattern = re.compile(r"\bSELECT\s+DISTINCT\s+", flags=re.IGNORECASE)
        if distinct_pattern.search(normalized_rewritten):
            if not _DISTINCT_ON_RE.search(normalized_rewritten):
                return True
        elif "DISTINCT" not in normalized_rewritten.upper():
            return True

    return False


def classify_static_subquery_wrapper_collapse(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if subquery wrapper is collapsed."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    subquery_match = _SUBQUERY_WRAPPER_RE.search(normalized_original)
    if subquery_match:
        original_select_count = normalized_original.upper().count("SELECT")
        rewritten_select_count = normalized_rewritten.upper().count("SELECT")
        if rewritten_select_count < original_select_count:
            return True

    return False


def classify_static_boolean_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if useless boolean expressions are simplified."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    if _BOOLEAN_CONSTANT_RE.search(normalized_original):
        if normalized_rewritten != normalized_original:
            return True

    return False


def classify_static_case_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if CASE WHEN is simplified."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    if _CASE_SIMPLIFY_RE.search(normalized_original):
        if normalized_rewritten.upper().count("CASE") < normalized_original.upper().count("CASE"):
            return True

    return False


def classify_static_coalesce_simplification(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if COALESCE is simplified."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    if _COALESCE_SIMPLIFY_RE.search(normalized_original):
        if normalized_rewritten.upper().count("COALESCE") < normalized_original.upper().count("COALESCE"):
            return True

    return False


def classify_static_expression_folding(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if constant expressions are folded."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    if _EXPRESSION_FOLDING_RE.search(normalized_original):
        original_ops = len(_EXPRESSION_FOLDING_RE.findall(normalized_original))
        rewritten_ops = len(_EXPRESSION_FOLDING_RE.findall(normalized_rewritten))
        if rewritten_ops < original_ops:
            return True

    return False


def classify_static_null_comparison(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> bool:
    """Classify if NULL comparisons are fixed."""
    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()
    if strategy_type != "EXACT_TEMPLATE_EDIT":
        return False

    if not original_sql or not rewritten_sql:
        return False

    normalized_original = normalize_sql(original_sql)
    normalized_rewritten = normalize_sql(rewritten_sql)

    if _NULL_COMPARISON_RE.search(normalized_original):
        if "IS NULL" in normalized_rewritten.upper() or "IS NOT NULL" in normalized_rewritten.upper():
            return True

    return False


def apply_static_alias_projection_cleanup_guard(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    rewrite_facts: dict[str, Any] | None,
    patchability: dict[str, Any] | None,
    selected_patch_strategy: dict[str, Any] | None,
    rewrite_materialization: dict[str, Any] | None,
    template_rewrite_ops: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """Apply guard for static alias projection cleanup.

    Returns modified patchability with blockingReasons if scope mismatch detected.
    Uses blockingReasons instead of eligible field.
    """
    alias_guarded, alias_family = classify_static_alias_projection_cleanup(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        selected_patch_strategy=selected_patch_strategy,
    )
    if not alias_guarded or alias_family is not None:
        return patchability, selected_patch_strategy, rewrite_materialization, list(template_rewrite_ops or [])

    guarded_patchability = dict(patchability or {})
    guarded_patchability["blockingReasons"] = ["STATIC_ALIAS_PROJECTION_CLEANUP_SCOPE_MISMATCH"]
    guarded_patchability["blockingReason"] = "STATIC_ALIAS_PROJECTION_CLEANUP_SCOPE_MISMATCH"
    guarded_patchability["allowedCapabilities"] = []
    return guarded_patchability, None, None, []


def dynamic_template_summary(
    rewrite_facts: dict[str, Any] | None,
    patchability: dict[str, Any] | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build dynamic template summary from rewrite facts and patchability.

    Uses blockingReasons to determine delivery class instead of eligible.
    """
    facts = dict((rewrite_facts or {}).get("dynamicTemplate") or {})
    profile = dict(facts.get("capabilityProfile") or {})
    if not facts:
        return None

    capability_tier = str(profile.get("capabilityTier") or "").strip() or None
    blocking_reason = (
        str((patchability or {}).get("dynamicBlockingReason") or "").strip()
        or str(profile.get("blockerFamily") or "").strip()
        or None
    )

    strategy_type = str((selected_patch_strategy or {}).get("strategyType") or "").strip().upper()

    # Check if patchable using blockingReasons instead of eligible
    blocking_reasons = list((patchability or {}).get("blockingReasons") or [])
    is_patchable = len(blocking_reasons) == 0

    delivery_class = None
    if strategy_type.startswith("DYNAMIC_") and is_patchable:
        delivery_class = "READY_DYNAMIC_PATCH"
    elif capability_tier == "SAFE_BASELINE" and blocking_reason and blocking_reason.endswith("NO_EFFECTIVE_DIFF"):
        delivery_class = "SAFE_BASELINE_NO_DIFF"
    elif capability_tier == "SAFE_BASELINE":
        delivery_class = "SAFE_BASELINE_BLOCKED"
    elif str(profile.get("shapeFamily") or "").strip():
        delivery_class = "REVIEW_ONLY"

    return {
        "present": bool(facts.get("present")),
        "shapeFamily": str(profile.get("shapeFamily") or "").strip() or None,
        "capabilityTier": capability_tier,
        "patchSurface": str(profile.get("patchSurface") or "").strip() or None,
        "baselineFamily": str(profile.get("baselineFamily") or "").strip() or None,
        "blockingReason": blocking_reason,
        "deliveryClass": delivery_class,
    }