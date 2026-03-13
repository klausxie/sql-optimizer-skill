from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import normalize_sql

_UNION_STRATEGY_RE = re.compile(r"simplify[_ ]?union|union", flags=re.IGNORECASE)
_DISTINCT_STRATEGY_RE = re.compile(
    r"distinct[_ ]?to[_ ]?group[_ ]?by|group[_ ]?by[_ ]?instead[_ ]?of[_ ]?distinct|replace\s+distinct\s+with\s+group\s+by",
    flags=re.IGNORECASE,
)
_UNION_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)
_GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", flags=re.IGNORECASE)
_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)


class AggregationTransformReviewOnlyRule:
    rule_id = "AGGREGATION_TRANSFORM_REVIEW_ONLY"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        strategy = str(candidate.get("rewriteStrategy") or "").strip()
        if not original_sql or not rewritten_sql:
            return None

        if _UNION_RE.search(original_sql) and _UNION_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate rewrites UNION semantics without a safe review-approved baseline",
            )

        if _DISTINCT_RE.search(original_sql) and _GROUP_BY_RE.search(rewritten_sql) and _DISTINCT_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate rewrites DISTINCT semantics into GROUP BY without a safe review-approved baseline",
            )
        return None
