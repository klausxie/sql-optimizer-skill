from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import aggregation_blockers, common_gate_failures


class DynamicStatementCanonicalEditCapabilityRule:
    capability = "DYNAMIC_STATEMENT_CANONICAL_EDIT"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        dynamic_profile = rewrite_facts.dynamic_template.capability_profile
        if not rewrite_facts.dynamic_template.present:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=150,
                reason=None,
            )

        failures = common_gate_failures(rewrite_facts) + aggregation_blockers(rewrite_facts)
        if failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=150,
                reason=failures[0],
            )

        if (
            dynamic_profile.capability_tier == "SAFE_BASELINE"
            and dynamic_profile.patch_surface == "STATEMENT_BODY"
            and dynamic_profile.template_preserving_candidate
        ):
            return CapabilityDecision(capability=self.capability, allowed=True, priority=150)

        blocker = dynamic_profile.blocker_family or "DYNAMIC_TEMPLATE_REVIEW_REQUIRED"
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=150,
            reason=f"DYNAMIC_TEMPLATE:{blocker}",
        )
