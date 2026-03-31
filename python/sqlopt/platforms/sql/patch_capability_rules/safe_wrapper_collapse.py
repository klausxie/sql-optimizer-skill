from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures, wrapper_blockers


class SafeWrapperCollapseCapabilityRule:
    capability = "SAFE_WRAPPER_COLLAPSE"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # If there's no wrapper query, this capability is not applicable
        if not rewrite_facts.wrapper_query.present:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=200,
                reason="WRAPPER_QUERY_ABSENT",
            )

        semantic_failures = common_gate_failures(rewrite_facts)
        wrapper_reasons = wrapper_blockers(rewrite_facts)
        if not semantic_failures and not wrapper_reasons:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=200)
        reason = (semantic_failures + wrapper_reasons)[0] if (semantic_failures or wrapper_reasons) else "PATCH_STRATEGY_UNAVAILABLE"
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=200,
            reason=reason,
        )
