"""Safe UNION Collapse Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import aggregation_blockers, common_gate_failures, dynamic_template_blockers, semantic_gate_ready


class SafeUnionCollapseCapabilityRule:
    """UNION 折叠能力规则

    检查是否可以使用 UNION 折叠策略。
    """

    capability = "SAFE_UNION_COLLAPSE"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        aggregation_reasons = aggregation_blockers(rewrite_facts)
        dynamic_reasons = dynamic_template_blockers(rewrite_facts)
        if semantic_gate_ready(rewrite_facts) and not aggregation_reasons and not dynamic_reasons:
            if rewrite_facts.effective_change:
                return CapabilityDecision(capability=self.capability, allowed=True, priority=250)
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=250,
                reason="NO_EFFECTIVE_CHANGE",
            )
        failures = common_gate_failures(rewrite_facts) + aggregation_reasons + dynamic_reasons
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=250,
            reason=failures[0] if failures else "PATCH_STRATEGY_UNAVAILABLE",
        )