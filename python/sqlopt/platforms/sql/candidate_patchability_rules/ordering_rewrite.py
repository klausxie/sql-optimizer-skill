from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class OrderingRewritePatchabilityRule:
    rule_id = "ORDERING_REWRITE_PATCHABLE"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if context.rewrite_strategy not in {"sort", "ORDER_BY_REWRITE"}:
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=5,
            reason="ordering rewrite is usually patchable",
        )
