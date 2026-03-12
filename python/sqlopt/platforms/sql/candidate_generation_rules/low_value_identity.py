from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import normalize_sql

_IDENTITY_STRATEGIES = {
    "none",
    "index_scan",
    "structure_preserving",
    "no_optimization_needed",
}


class IdentityNoopRule:
    rule_id = "IDENTITY_NOOP"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
        strategy = str(candidate.get("rewriteStrategy") or "").strip().lower()
        if strategy == "opencode_text_fallback":
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id="CANONICAL_NOOP_HINT",
                category="CANONICAL_NOOP_HINT",
                reason="text fallback is diagnostics only and not a consumable sql candidate",
            )
        if not rewritten_sql:
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="IDENTITY_NOOP",
                reason="candidate has no rewritten sql",
            )
        if normalize_sql(rewritten_sql) != normalize_sql(context.original_sql):
            return None
        if strategy in _IDENTITY_STRATEGIES or not strategy:
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="IDENTITY_NOOP",
                reason="candidate is structurally identical to the original sql",
            )
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id="CANONICAL_NOOP_HINT",
            category="CANONICAL_NOOP_HINT",
            reason="candidate only restates the original sql without a material change",
        )
