"""Safe EXISTS Rewrite Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeExistsRewriteCapabilityRule:
    """EXISTS 重写能力规则

    检查是否可以使用 EXISTS 重写策略。
    """

    capability = "SAFE_EXISTS_REWRITE"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查通用语义门失败
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            reason = semantic_failures[0]
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=260,  # 高于 UNION (250)
                reason=reason,
            )

        # 检查是否存在有效变化
        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=260)

        # 没有有效变化，不允许
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=260,
            reason="NO_EFFECTIVE_CHANGE",
        )