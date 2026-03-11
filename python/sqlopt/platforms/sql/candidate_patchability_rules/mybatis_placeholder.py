from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class MyBatisPlaceholderPreservedRule:
    rule_id = "MYBATIS_PLACEHOLDER_PRESERVED"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if "#{" not in context.original_sql or "#{" not in context.rewritten_sql:
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=10,
            reason="mybatis placeholders are preserved",
        )
