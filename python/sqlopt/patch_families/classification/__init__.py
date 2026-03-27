# python/sqlopt/patch_families/classification/__init__.py
"""Configuration-driven patch family classification."""
from __future__ import annotations

from .models import ClassificationConfig, ClassificationContext


def classify_patch_family(ctx: ClassificationContext) -> str | None:
    """主分类函数，暂时返回 None"""
    # TODO: 实现配置匹配逻辑
    return None


__all__ = [
    "ClassificationConfig",
    "ClassificationContext",
    "classify_patch_family",
]