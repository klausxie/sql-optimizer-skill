from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class GenericPlaceholderPenaltyRule:
    rule_id = "GENERIC_PLACEHOLDER_PENALTY"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if "?" not in context.rewritten_sql or "#{" in context.rewritten_sql:
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=-20,
            reason="generic placeholders reduce mapper patch stability",
        )
