from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class RuleSourcePatchabilityRule:
    rule_id = "RULE_SOURCE_CONSERVATIVE"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if context.candidate_source != "rule":
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=15,
            reason="rule-generated candidate is structurally conservative",
        )
