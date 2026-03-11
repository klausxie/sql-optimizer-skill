from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class JoinHeavyPenaltyRule:
    rule_id = "JOIN_HEAVY_PATCH_SURFACE"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if " join " not in context.rewritten_sql.lower():
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=-10,
            reason="join-heavy rewrite expands structural patch surface",
        )
