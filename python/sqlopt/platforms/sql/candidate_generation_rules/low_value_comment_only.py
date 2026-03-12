from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..canonicalization_support import normalize_sql, strip_sql_comments


def _comment_stripped_normalized_sql(value: str) -> str:
    return normalize_sql(strip_sql_comments(value))


class CommentOnlyRewriteRule:
    rule_id = "COMMENT_ONLY_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
        if not rewritten_sql:
            return None
        if _comment_stripped_normalized_sql(rewritten_sql) != _comment_stripped_normalized_sql(context.original_sql):
            return None
        if normalize_sql(rewritten_sql) == normalize_sql(context.original_sql):
            return None
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id=self.rule_id,
            category="CANONICAL_NOOP_HINT",
            reason="candidate only changes sql comments or annotations without a material sql change",
        )
