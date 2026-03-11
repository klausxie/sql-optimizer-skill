from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class ProjectionRewritePatchabilityRule:
    rule_id = "PROJECTION_REWRITE_PATCHABLE"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        if context.rewrite_strategy not in {"PROJECT_COLUMNS", "projection"}:
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=15,
            reason="projection-style rewrite is easy to patch",
        )
