from __future__ import annotations

from ..canonicalization_models import CanonicalContext, CanonicalMatch
from ..canonicalization_support import (
    DISTINCT_DIRECT_RE,
    DISTINCT_WRAPPER_RE,
    normalize_sql,
    redundant_subquery_blockers,
    split_select_list,
    strip_projection_alias,
)
from .base import CanonicalRule


class RedundantDistinctCanonicalRule(CanonicalRule):
    rule_id = "REDUNDANT_DISTINCT_WRAPPER_CANONICAL_FORM"

    def evaluate(self, context: CanonicalContext) -> CanonicalMatch | None:
        if context.fingerprint_strength != "EXACT":
            return None

        wrapper_match = DISTINCT_WRAPPER_RE.match(context.normalized_original_sql)
        direct_match = DISTINCT_DIRECT_RE.match(context.normalized_rewritten_sql)
        if wrapper_match is None or direct_match is None:
            return None

        outer_select = [strip_projection_alias(x) for x in split_select_list(wrapper_match.group("outer_select"))]
        inner_select = [strip_projection_alias(x) for x in split_select_list(wrapper_match.group("inner_select"))]
        direct_select = [strip_projection_alias(x) for x in split_select_list(direct_match.group("select"))]
        inner_from = normalize_sql(wrapper_match.group("inner_from"))
        outer_suffix = normalize_sql(wrapper_match.group("outer_suffix") or "")
        direct_from = normalize_sql(direct_match.group("from"))
        blockers = redundant_subquery_blockers(inner_from)
        expected_from = normalize_sql(f"{inner_from} {outer_suffix}".strip())

        if blockers:
            return None
        if outer_select != inner_select or inner_select != direct_select:
            return None
        if direct_from != expected_from:
            return None
        return CanonicalMatch(
            rule_id=self.rule_id,
            preferred_direction="REMOVE_REDUNDANT_DISTINCT_WRAPPER",
            score_delta=14,
            reason="direct query removes redundant distinct wrapper",
        )
