from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import aggregation_blockers, common_gate_failures, dynamic_template_blockers, semantic_gate_ready


class ExactTemplateEditCapabilityRule:
    capability = "EXACT_TEMPLATE_EDIT"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        aggregation_reasons = aggregation_blockers(rewrite_facts)
        dynamic_reasons = dynamic_template_blockers(rewrite_facts)
        aggregation = rewrite_facts.aggregation_query
        if (
            semantic_gate_ready(rewrite_facts)
            and not dynamic_reasons
            and aggregation.present
            and aggregation.distinct_present
            and not aggregation.group_by_present
            and not aggregation.having_present
            and not aggregation.window_present
            and not aggregation.union_present
            and str(aggregation.capability_profile.constraint_family or "").strip().upper() == "DISTINCT_AGGREGATION"
            and rewrite_facts.effective_change
        ):
            return CapabilityDecision(capability=self.capability, allowed=True, priority=100)
        if semantic_gate_ready(rewrite_facts) and not aggregation_reasons and not dynamic_reasons:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=100)
        failures = common_gate_failures(rewrite_facts) + aggregation_reasons + dynamic_reasons
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=100,
            reason=failures[0] if failures else "PATCH_STRATEGY_UNAVAILABLE",
        )
