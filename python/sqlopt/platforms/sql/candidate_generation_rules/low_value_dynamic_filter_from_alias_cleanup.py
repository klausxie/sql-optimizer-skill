from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import dynamic_filter_from_alias_cleanup_sql, normalize_sql


class DynamicFilterFromAliasCleanupRewriteRule:
    rule_id = "DYNAMIC_FILTER_FROM_ALIAS_NOISE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        canonical_sql = dynamic_filter_from_alias_cleanup_sql(context.original_sql)
        if not canonical_sql:
            return None
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        if not rewritten_sql or rewritten_sql == normalize_sql(canonical_sql):
            return None
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id=self.rule_id,
            category="DYNAMIC_FILTER_FROM_ALIAS_NOISE",
            reason="dynamic filter from-alias cleanup baseline only accepts the canonical alias-removal rewrite",
        )
