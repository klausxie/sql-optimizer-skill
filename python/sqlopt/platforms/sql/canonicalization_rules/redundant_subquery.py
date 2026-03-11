from __future__ import annotations

from ..canonicalization_models import CanonicalContext, CanonicalMatch
from ..canonicalization_support import (
    COUNT_DIRECT_RE,
    COUNT_DIRECT_SUFFIX_RE,
    COUNT_WRAPPER_RE,
    SELECT_DIRECT_RE,
    SELECT_WRAPPER_RE,
    extract_from_suffix,
    normalize_sql,
    redundant_subquery_blockers,
    split_select_list,
    strip_projection_alias,
)
from .base import CanonicalRule


class RedundantSubqueryCanonicalRule(CanonicalRule):
    rule_id = "REDUNDANT_SUBQUERY_CANONICAL_FORM"

    def evaluate(self, context: CanonicalContext) -> CanonicalMatch | None:
        if context.fingerprint_strength != "EXACT":
            return None

        wrapper_original = COUNT_WRAPPER_RE.match(context.normalized_original_sql)
        count_direct = COUNT_DIRECT_RE.match(context.normalized_rewritten_sql)
        if wrapper_original and count_direct:
            inner_normalized = normalize_sql(wrapper_original.group("inner"))
            direct_match = COUNT_DIRECT_SUFFIX_RE.match(context.normalized_rewritten_sql)
            direct_suffix = normalize_sql(direct_match.group("from")) if direct_match is not None else ""
            inner_suffix = extract_from_suffix(inner_normalized)
            if inner_suffix:
                blockers = redundant_subquery_blockers(inner_suffix)
                if not blockers and inner_suffix == direct_suffix:
                    return CanonicalMatch(
                        rule_id=self.rule_id,
                        preferred_direction="REMOVE_REDUNDANT_WRAPPER",
                        score_delta=12,
                        reason="direct query removes redundant count wrapper",
                    )

        wrapper_select = SELECT_WRAPPER_RE.match(context.normalized_original_sql)
        alias_direct = SELECT_DIRECT_RE.match(context.normalized_rewritten_sql)
        if wrapper_select and alias_direct:
            outer_select = [strip_projection_alias(x) for x in split_select_list(wrapper_select.group("outer_select"))]
            inner_select = [strip_projection_alias(x) for x in split_select_list(wrapper_select.group("inner_select"))]
            direct_select = [strip_projection_alias(x) for x in split_select_list(alias_direct.group("select"))]
            inner_from = normalize_sql(wrapper_select.group("inner_from"))
            direct_from = normalize_sql(alias_direct.group("from"))
            blockers = redundant_subquery_blockers(inner_from)
            if not blockers and outer_select == inner_select == direct_select and inner_from == direct_from:
                return CanonicalMatch(
                    rule_id=self.rule_id,
                    preferred_direction="REMOVE_REDUNDANT_WRAPPER",
                    score_delta=12,
                    reason="direct query removes redundant subquery wrapper",
                )

        return None
