from __future__ import annotations

from ..canonicalization_models import CanonicalContext, CanonicalMatch
from ..canonicalization_support import SELECT_DIRECT_RE, split_select_list, strip_projection_alias
from .base import CanonicalRule


class AliasOnlyCanonicalRule(CanonicalRule):
    rule_id = "ALIAS_ONLY_CANONICAL_FORM"

    def evaluate(self, context: CanonicalContext) -> CanonicalMatch | None:
        alias_direct = SELECT_DIRECT_RE.match(context.normalized_rewritten_sql)
        if alias_direct is None:
            return None
        select_items = split_select_list(alias_direct.group("select"))
        if not select_items:
            return None
        stripped_items = [strip_projection_alias(item) for item in select_items]
        alias_count = sum(1 for item, stripped in zip(select_items, stripped_items) if item != stripped)
        if alias_count != 0:
            return None
        return CanonicalMatch(
            rule_id=self.rule_id,
            preferred_direction="MINIMIZE_REDUNDANT_ALIAS",
            score_delta=6,
            reason="projection avoids redundant aliases",
        )
