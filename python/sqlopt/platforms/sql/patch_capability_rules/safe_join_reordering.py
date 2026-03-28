"""Safe JOIN Reordering Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinReorderingCapability:
    """JOIN 重排能力规则"""

    capability = "SAFE_JOIN_REORDERING"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=260,
                reason=semantic_failures[0],
            )

        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=260)

        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=260,
            reason="NO_EFFECTIVE_CHANGE",
        )