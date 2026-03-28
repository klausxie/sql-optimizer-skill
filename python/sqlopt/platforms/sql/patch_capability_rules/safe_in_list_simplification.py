"""Safe IN List Simplification Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import aggregation_blockers, common_gate_failures, dynamic_template_blockers, semantic_gate_ready


class SafeInListSimplificationCapability:
    """IN 列表简化能力规则

    检查是否可以使用 IN 列表简化策略。
    """

    capability = "SAFE_IN_LIST_SIMPLIFICATION"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        aggregation_reasons = aggregation_blockers(rewrite_facts)
        dynamic_reasons = dynamic_template_blockers(rewrite_facts)
        if semantic_gate_ready(rewrite_facts) and not aggregation_reasons and not dynamic_reasons:
            if rewrite_facts.effective_change:
                return CapabilityDecision(capability=self.capability, allowed=True, priority=230)
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=230,
                reason="NO_EFFECTIVE_CHANGE",
            )
        failures = common_gate_failures(rewrite_facts) + aggregation_reasons + dynamic_reasons
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=230,
            reason=failures[0] if failures else "PATCH_STRATEGY_UNAVAILABLE",
        )