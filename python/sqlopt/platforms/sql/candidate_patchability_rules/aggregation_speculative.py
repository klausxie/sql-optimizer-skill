from __future__ import annotations

import re

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch

_AGGREGATIONISH_RE = re.compile(
    r"\bgroup\s+by\b|\bhaving\b|\bover\s*\(|\bunion\b|\bselect\s+distinct\b|^\s*with\b",
    flags=re.IGNORECASE | re.DOTALL,
)
_WHERE_RE = re.compile(r"\bwhere\b", flags=re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\b", flags=re.IGNORECASE)
_SPECULATIVE_STRATEGY_RE = re.compile(r"ADD_(?:FILTER|LIMIT|TIME_FILTER)", flags=re.IGNORECASE)


class AggregationSpeculativePenaltyRule:
    rule_id = "AGGREGATION_SPECULATIVE_PENALTY"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        original_sql = str(context.original_sql or "")
        rewritten_sql = str(context.rewritten_sql or "")
        if not _AGGREGATIONISH_RE.search(original_sql):
            return None
        adds_where = _WHERE_RE.search(rewritten_sql) and not _WHERE_RE.search(original_sql)
        adds_limit = _LIMIT_RE.search(rewritten_sql) and not _LIMIT_RE.search(original_sql)
        speculative_strategy = _SPECULATIVE_STRATEGY_RE.search(context.rewrite_strategy or "") is not None
        if not speculative_strategy and not adds_where and not adds_limit:
            return None
        return CandidatePatchabilityRuleMatch(
            rule_id=self.rule_id,
            score_delta=-25,
            reason="aggregation-heavy SQL should not prefer speculative filter or limit rewrites",
        )
