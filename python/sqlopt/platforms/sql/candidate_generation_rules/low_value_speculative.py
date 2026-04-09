from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import AGGREGATIONISH_SQL_RE, LIMIT_RE, WHERE_RE, normalize_sql, normalize_strategy_text

_SPECULATIVE_STRATEGY_RE = re.compile(
    r"add_(?:filter|limit|time_filter|where|safe_limit)|combined_optimization|group_by_instead_of_distinct",
    flags=re.IGNORECASE,
)
_SUPPORTED_CHOOSE_UNSUPPORTED_STRATEGY_RE = re.compile(
    r"index[_ ]?driven[_ ]?union|union[_ ]?index",
    flags=re.IGNORECASE,
)
_SUPPORTED_CHOOSE_BRANCH_MERGE_RE = re.compile(
    r"union[_ ]?or[_ ]?elimination|or[_ ]?elimination",
    flags=re.IGNORECASE,
)
_SUPPORTED_CHOOSE_NO_BASELINE_RE = re.compile(
    r"redundant[_ ]?condition[_ ]?removal|predicate|condition",
    flags=re.IGNORECASE,
)


def classify_supported_choose_guarded_filter_strategy(strategy: str | None) -> tuple[str, str] | None:
    normalized_strategy = normalize_strategy_text(strategy)
    if not normalized_strategy:
        return None
    if _SUPPORTED_CHOOSE_UNSUPPORTED_STRATEGY_RE.search(normalized_strategy):
        return (
            "UNSUPPORTED_STRATEGY",
            "candidate uses an unsupported union/index strategy on a supported choose-guarded filter",
        )
    if _SUPPORTED_CHOOSE_BRANCH_MERGE_RE.search(normalized_strategy):
        return (
            "SEMANTIC_RISK_REWRITE",
            "candidate merges choose branches on a supported choose-guarded filter without a template-preserving safe path",
        )
    if _SUPPORTED_CHOOSE_NO_BASELINE_RE.search(normalized_strategy):
        return (
            "NO_SAFE_BASELINE_MATCH",
            "candidate rewrites choose-guarded filter predicates but does not match any supported template-preserving baseline",
        )
    return None


class SpeculativeAdditiveRewriteRule:
    rule_id = "SPECULATIVE_ADDITIVE_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        strategy = normalize_strategy_text(candidate.get("rewriteStrategy") or "")
        if not rewritten_sql:
            return None
        if not AGGREGATIONISH_SQL_RE.search(original_sql):
            return None
        adds_where = bool(WHERE_RE.search(rewritten_sql) and not WHERE_RE.search(original_sql))
        adds_limit = bool(LIMIT_RE.search(rewritten_sql) and not LIMIT_RE.search(original_sql))
        if not (adds_where or adds_limit or _SPECULATIVE_STRATEGY_RE.search(strategy)):
            return None
        return LowValueAssessment(
            candidate_id=str(candidate.get("id") or ""),
            rule_id=self.rule_id,
            category="SPECULATIVE_ADDITIVE_REWRITE",
            reason="candidate adds speculative filters or limits on a complex sql shape",
        )
