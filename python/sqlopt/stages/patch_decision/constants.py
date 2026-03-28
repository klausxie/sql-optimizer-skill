"""
Patch Decision Constants

ReasonCode 枚举和 DeliveryTier 定义，集中管理所有 patch 决策相关常量。
"""

from __future__ import annotations

from enum import Enum


class GateResultStatus(Enum):
    """门控执行结果状态"""
    PASS = "GATE_PASS"  # 门控通过
    SKIP = "GATE_SKIP"  # 跳过（阻断）
    BLOCK = "GATE_BLOCK"  # 阻止（严重错误）


class DeliveryTier(Enum):
    """补丁交付层级"""
    READY_TO_APPLY = "READY_TO_APPLY"  # 可直接应用
    BLOCKED = "BLOCKED"  # 被阻断
    PATCHABLE_WITH_REWRITE = "PATCHABLE_WITH_REWRITE"  # 通过重写可修复
    MANUAL_REVIEW = "MANUAL_REVIEW"  # 需人工审查


class ReasonCode:
    """
    Patch 决策原因码

    所有原因码集中定义，便于搜索和维护。
    """

    # === Locator 相关 (Gate 1) ===
    PATCH_LOCATOR_AMBIGUOUS = "PATCH_LOCATOR_AMBIGUOUS"

    # === Acceptance 状态相关 (Gate 2) ===
    PATCH_CONFLICT_NO_CLEAR_WINNER = "PATCH_CONFLICT_NO_CLEAR_WINNER"

    # === Semantic 语义等价相关 (Gate 3) ===
    PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS = "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS"
    PATCH_SEMANTIC_CONFIDENCE_LOW = "PATCH_SEMANTIC_CONFIDENCE_LOW"

    # === Change 有效变更相关 (Gate 5) ===
    PATCH_NO_EFFECTIVE_CHANGE = "PATCH_NO_EFFECTIVE_CHANGE"

    # === Template 模板重复相关 (Gate 6) ===
    PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED = "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED"

    # === Dynamic 动态模板相关 (Gate 7) ===
    PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE = "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"
    PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE = "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE"

    # === Security 安全相关 ===
    PATCH_VALIDATION_BLOCKED_SECURITY = "PATCH_VALIDATION_BLOCKED_SECURITY"

    # === Placeholder 占位符相关 (Gate 8) ===
    PATCH_PLACEHOLDER_MISMATCH = "PATCH_PLACEHOLDER_MISMATCH"

    # === Build 构建相关 (Gate 9) ===
    PATCH_BUILD_FAILED = "PATCH_BUILD_FAILED"

    @classmethod
    def all(cls) -> list[str]:
        """获取所有原因码列表"""
        return [
            v for k, v in cls.__dict__.items()
            if k.isupper() and isinstance(v, str)
        ]

    @classmethod
    def map_to_tier(cls, reason_code: str | None) -> str:
        """将原因码映射到交付层级"""
        if not reason_code:
            return DeliveryTier.BLOCKED.value

        tier_map = {
            "SECURITY": DeliveryTier.PATCHABLE_WITH_REWRITE.value,
            "REVIEW": DeliveryTier.MANUAL_REVIEW.value,
            "CONFLICT": DeliveryTier.BLOCKED.value,
            "NO_CLEAR": DeliveryTier.BLOCKED.value,
            "NO_EFFECTIVE": DeliveryTier.BLOCKED.value,
            "LOCATOR": DeliveryTier.BLOCKED.value,
            "SEMANTIC": DeliveryTier.BLOCKED.value,
            "TEMPLATE": DeliveryTier.BLOCKED.value,
            "DYNAMIC": DeliveryTier.MANUAL_REVIEW.value,
            "INCLUDE": DeliveryTier.MANUAL_REVIEW.value,
        }

        for prefix, tier in tier_map.items():
            if prefix in reason_code:
                return tier

        return DeliveryTier.BLOCKED.value