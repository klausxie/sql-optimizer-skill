# python/sqlopt/patch_families/classification/models.py
"""Data models for classification configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ClassificationConfig:
    """单个 family 的分类配置"""
    family: str  # FAMILY_ID (e.g., "STATIC_IN_LIST_SIMPLIFICATION")
    strategy_type: str | None = None  # patch strategy type (e.g., "EXACT_TEMPLATE_EDIT")
    original_patterns: list[str] | None = None  # regex patterns to match original_sql
    rewritten_patterns: list[str] | None = None  # regex patterns to match rewritten_sql
    validator_func: str | None = None  # fallback: validator function name
    requires_rewrite_facts: bool = False  # 是否需要 rewrite_facts
    requires_dynamic_template: bool = False


@dataclass
class ClassificationContext:
    """分类上下文，封装所有输入参数"""
    original_sql: str
    rewritten_sql: str | None
    rewrite_facts: dict[str, Any] | None = None
    selected_patch_strategy: dict[str, Any] | None = None