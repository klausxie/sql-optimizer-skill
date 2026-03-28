"""Safe JOIN Consolidation Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinConsolidationCapability:
    """JOIN 合并能力规则"""

    capability = "SAFE_JOIN_CONSOLIDATION"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=255,
                reason=semantic_failures[0],
            )

        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=255)

        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=255,
            reason="NO_EFFECTIVE_CHANGE",
        )