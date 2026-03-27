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