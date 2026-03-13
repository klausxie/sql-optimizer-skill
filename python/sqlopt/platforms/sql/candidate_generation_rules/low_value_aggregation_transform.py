from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import normalize_sql

_UNION_STRATEGY_RE = re.compile(r"simplify[_ ]?union|union", flags=re.IGNORECASE)
_DISTINCT_STRATEGY_RE = re.compile(
    r"distinct[_ ]?to[_ ]?group[_ ]?by|group[_ ]?by[_ ]?instead[_ ]?of[_ ]?distinct|replace[_ ]?distinct[_ ]?with[_ ]?group[_ ]?by|group[_ ]?by[_ ]?index[_ ]?scan",
    flags=re.IGNORECASE,
)
_AGGREGATION_INDEX_HINT_STRATEGY_RE = re.compile(
    r"index\s+hint|index[_ ]?scan|index[_ ]?optimization|group[_ ]?by.+index",
    flags=re.IGNORECASE,
)
_WINDOW_STRATEGY_RE = re.compile(
    r"window[_ ]?clause[_ ]?extract|extract[_ ]?window|window[_ ]?rewrite|window[_ ]?alias",
    flags=re.IGNORECASE,
)
_ORDERING_STRATEGY_RE = re.compile(
    r"remove[_ ]?redundant[_ ]?order[_ ]?by|drop[_ ]?order[_ ]?by|redundant[_ ]?order[_ ]?by",
    flags=re.IGNORECASE,
)
_UNION_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)
_GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", flags=re.IGNORECASE)
_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)
_HAVING_RE = re.compile(r"\bhaving\b", flags=re.IGNORECASE)
_WINDOW_RE = re.compile(r"\bover\s*\(", flags=re.IGNORECASE)


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

        if (_GROUP_BY_RE.search(original_sql) or _HAVING_RE.search(original_sql)) and _AGGREGATION_INDEX_HINT_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate applies aggregation-specific index or hint advice without a safe review-approved baseline",
            )

        if (_GROUP_BY_RE.search(original_sql) or _HAVING_RE.search(original_sql)) and _ORDERING_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="CANONICAL_NOOP_HINT",
                reason="candidate removes ORDER BY from an aggregation review-only query without a safe delivery baseline",
            )

        if _WINDOW_RE.search(original_sql) and _WINDOW_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="CANONICAL_NOOP_HINT",
                reason="candidate rewrites window syntax without a safe review-approved delivery baseline",
            )
        return None
