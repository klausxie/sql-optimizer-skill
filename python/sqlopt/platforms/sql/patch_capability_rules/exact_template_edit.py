from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures, semantic_gate_ready


class ExactTemplateEditCapabilityRule:
    capability = "EXACT_TEMPLATE_EDIT"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        if semantic_gate_ready(rewrite_facts):
            return CapabilityDecision(capability=self.capability, allowed=True, priority=100)
        failures = common_gate_failures(rewrite_facts)
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=100,
            reason=failures[0] if failures else "PATCH_STRATEGY_UNAVAILABLE",
        )
