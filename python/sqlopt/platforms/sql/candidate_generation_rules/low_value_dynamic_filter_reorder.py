from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import simple_where_predicate_signature
from .low_value_dynamic_filter import _dynamic_filter_features


class DynamicFilterPredicateReorderRule:
    rule_id = "DYNAMIC_FILTER_PREDICATE_REORDER"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        features = _dynamic_filter_features(context)
        if "WHERE" not in features:
            return None

        original_signature = simple_where_predicate_signature(context.original_sql)
        rewritten_signature = simple_where_predicate_signature(str(candidate.get("rewrittenSql") or ""))
        if original_signature is None or rewritten_signature is None:
            return None
        if original_signature != rewritten_signature:
            return None

        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id=self.rule_id,
            category="CANONICAL_NOOP_HINT",
            reason="candidate only reorders simple AND predicates on a dynamic filter template",
        )
