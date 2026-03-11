from __future__ import annotations

from typing import Protocol

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch


class CandidatePatchabilityRule(Protocol):
    rule_id: str

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        ...
