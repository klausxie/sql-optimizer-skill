# python/sqlopt/patch_families/classification/registry.py
"""Configuration registry and dispatcher for patch family classification."""
from __future__ import annotations

import re
from typing import Any

from .models import ClassificationConfig, ClassificationContext


# 配置注册表 - 简单的 regex-based family
_CONFIG: dict[str, ClassificationConfig] = {
    "STATIC_IN_LIST_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_IN_LIST_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\b([a-z_][a-z0-9_\.]*)\s+IN\s*\(\s*([^,\)]+)\s*\)",  # column IN (value)
            r"\b([a-z_][a-z0-9_\.]*)\s+NOT\s+IN\s*\(\s*([^,\)]+)\s*\)",  # column NOT IN (value)
        ],
        rewritten_patterns=[
            r"=\s+[^,\)]+",   # column = value (no \b before =)
            r"<>?\s+[^,\)]+",  # column <> value
            r"!=\s+[^,\)]+",  # column != value
        ],
    ),
    "STATIC_LIMIT_OPTIMIZATION": ClassificationConfig(
        family="STATIC_LIMIT_OPTIMIZATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\bLIMIT\s+0\s*($|;|\))",  # LIMIT 0
            r"\bLIMIT\s+(\d{10,}|\d{1,9}[0-9]{3,})\s*($|;|\))",  # LIMIT large
        ],
        rewritten_patterns=[],  # removed
    ),
    "STATIC_ORDER_BY_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_ORDER_BY_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\bORDER\s+BY\s+(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+)(\s*,\s*(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+))*",
        ],
        rewritten_patterns=[],  # removed
    ),
    "STATIC_DISTINCT_ON_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_DISTINCT_ON_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bSELECT\s+DISTINCT\s+ON\s*\("],
        rewritten_patterns=[r"\bSELECT\s+DISTINCT\s+"],
    ),
    "STATIC_OR_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_OR_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b([a-z_][a-z0-9_\.]*)\s*=\s*[^'\s]+\s+OR\s+\1\s*=\s*[^'\s]+"],
        rewritten_patterns=[r"\bIN\s*\("],
    ),
    "STATIC_BOOLEAN_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_BOOLEAN_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b(1\s*=\s*1|0\s*=\s*0|1\s*<>?\s*1|0\s*<>?\s*0)\b"],
        rewritten_patterns=[],  # removed or simplified
    ),
    "STATIC_CASE_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_CASE_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bCASE\s+WHEN\s+TRUE\s+THEN\b"],
        rewritten_patterns=[],  # simplified
    ),
    "STATIC_COALESCE_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_COALESCE_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bCOALESCE\s*\(\s*([a-z_][a-z0-9_\.]*)\s*,\s*(\1|NULL)\s*\)"],
        rewritten_patterns=[r"\1"],  # simplified to just the column
    ),
    "STATIC_EXPRESSION_FOLDING": ClassificationConfig(
        family="STATIC_EXPRESSION_FOLDING",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b(\d+)\s*([+\-*/])\s*(\d+)\b"],
        rewritten_patterns=[],  # folded result
    ),
    "STATIC_NULL_COMPARISON": ClassificationConfig(
        family="STATIC_NULL_COMPARISON",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b([a-z_][a-z0-9_\.]*)\s*(=|<>|!=)\s*NULL\b"],
        rewritten_patterns=[r"\bIS\s+(NULL|NOT\s+NULL)\b"],
    ),
}


def normalize_sql(sql: str) -> str:
    """Normalize SQL for pattern matching."""
    if not sql:
        return ""
    # Simple normalization: lowercase, collapse whitespace
    return re.sub(r"\s+", " ", sql.strip().lower())


def _matches_config(ctx: ClassificationContext, cfg: ClassificationConfig) -> bool:
    """Check if context matches configuration."""
    if not ctx.original_sql:
        return False

    # Check strategy type
    if cfg.strategy_type:
        strategy = (ctx.selected_patch_strategy or {}).get("strategyType", "").strip().upper()
        if strategy != cfg.strategy_type.upper():
            return False

    # Normalize SQL
    norm_original = normalize_sql(ctx.original_sql)
    norm_rewritten = normalize_sql(ctx.rewritten_sql or "")

    # Check original patterns
    if cfg.original_patterns:
        original_matched = any(
            re.search(pattern, norm_original, re.IGNORECASE)
            for pattern in cfg.original_patterns
        )
        if not original_matched:
            return False

    # Check rewritten patterns (if specified)
    if cfg.rewritten_patterns is not None:
        if cfg.rewritten_patterns:  # Non-empty list - need to match
            rewritten_matched = any(
                re.search(pattern, norm_rewritten, re.IGNORECASE)
                for pattern in cfg.rewritten_patterns
            )
            if not rewritten_matched:
                return False
        else:  # Empty list - rewritten should NOT match original patterns
            # This is a simplification case (pattern removed)
            pass

    return True


def classify_patch_family(ctx: ClassificationContext) -> str | None:
    """Main classification function: config-first, then fallback."""
    # Configuration-based matching
    for family, cfg in _CONFIG.items():
        if _matches_config(ctx, cfg):
            return family

    # Fallback: return None (let existing validator_sql logic handle it)
    return None