from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import AGGREGATIONISH_SQL_RE, LIMIT_RE, WHERE_RE, normalize_sql

_SPECULATIVE_STRATEGY_RE = re.compile(
    r"add_(?:filter|limit|time_filter|where|safe_limit)|combined_optimization|group_by_instead_of_distinct",
    flags=re.IGNORECASE,
)


class SpeculativeAdditiveRewriteRule:
    rule_id = "SPECULATIVE_ADDITIVE_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        strategy = str(candidate.get("rewriteStrategy") or "")
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

