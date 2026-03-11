from __future__ import annotations

from ..canonicalization_models import CanonicalContext, CanonicalMatch
from ..canonicalization_support import COUNT_DIRECT_RE, normalize_sql
from .base import CanonicalRule


class CountCanonicalRule(CanonicalRule):
    rule_id = "COUNT_CANONICAL_FORM"

    def evaluate(self, context: CanonicalContext) -> CanonicalMatch | None:
        if context.fingerprint_strength != "EXACT":
            return None
        count_direct = COUNT_DIRECT_RE.match(context.normalized_rewritten_sql)
        if count_direct is None:
            return None
        arg = normalize_sql(count_direct.group("arg")).lower()
        if arg == "*":
            score_delta = 15
            reason = "count(*) is preferred as canonical count form"
        elif arg == "1":
            score_delta = 10
            reason = "count(1) is acceptable but less canonical than count(*)"
        else:
            score_delta = 5
            reason = "direct count form is preferred over column-specific count"
        return CanonicalMatch(
            rule_id=self.rule_id,
            preferred_direction="COUNT_STAR_FIRST",
            score_delta=score_delta,
            reason=reason,
        )
