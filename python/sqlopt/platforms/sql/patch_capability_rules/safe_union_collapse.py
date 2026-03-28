"""Safe UNION Collapse Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeUnionCollapseCapabilityRule:
    """UNION 折叠能力规则

    检查是否可以使用 UNION 折叠策略。
    """

    capability = "SAFE_UNION_COLLAPSE"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查通用语义门失败
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            reason = semantic_failures[0]
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=250,  # 高于 WRAPPER_COLLAPSE (200)
                reason=reason,
            )

        # 检查是否有 UNION 相关的重写事实
        # 如果没有明确的 UNION 包装模式，则不允许
        # 这里的逻辑由 rewrite_facts 决定
        # 如果存在有效变化，允许 UNION 折叠
        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=250)

        # 没有有效变化，不允许
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=250,
            reason="NO_EFFECTIVE_CHANGE",
        )