"""Safe LEFT to INNER JOIN Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import aggregation_blockers, common_gate_failures, dynamic_template_blockers, semantic_gate_ready


class SafeJoinLeftToInnerCapability:
    """LEFT JOIN 转 INNER JOIN 能力规则

    检查是否可以将 LEFT JOIN 转换为 INNER JOIN。
    """

    capability = "SAFE_JOIN_LEFT_TO_INNER"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查聚合和动态模板阻塞
        aggregation_reasons = aggregation_blockers(rewrite_facts)
        dynamic_reasons = dynamic_template_blockers(rewrite_facts)
        if semantic_gate_ready(rewrite_facts) and not aggregation_reasons and not dynamic_reasons:
            if rewrite_facts.effective_change:
                return CapabilityDecision(capability=self.capability, allowed=True, priority=270)
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=270,
                reason="NO_EFFECTIVE_CHANGE",
            )
        # 有阻塞因素
        failures = common_gate_failures(rewrite_facts) + aggregation_reasons + dynamic_reasons
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=270,
            reason=failures[0] if failures else "PATCH_STRATEGY_UNAVAILABLE",
        )