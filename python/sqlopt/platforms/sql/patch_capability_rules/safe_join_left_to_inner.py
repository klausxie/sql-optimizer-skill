"""Safe LEFT to INNER JOIN Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinLeftToInnerCapability:
    """LEFT JOIN 转 INNER JOIN 能力规则

    检查是否可以将 LEFT JOIN 转换为 INNER JOIN。
    """

    capability = "SAFE_JOIN_LEFT_TO_INNER"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查通用语义门失败
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=270,
                reason=semantic_failures[0],
            )

        # 检查是否存在有效变化
        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=270)

        # 没有有效变化，不允许
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=270,
            reason="NO_EFFECTIVE_CHANGE",
        )