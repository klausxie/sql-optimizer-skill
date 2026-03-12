from __future__ import annotations

from ..candidate_patchability_models import CandidatePatchabilityContext, CandidatePatchabilityRuleMatch
from ..canonicalization_support import (
    DISTINCT_WRAPPER_RE,
    GROUP_BY_WRAPPER_RE,
    HAVING_WRAPPER_RE,
    SELECT_WRAPPER_RE,
    normalize_sql,
    redundant_groupby_wrapper_blockers,
    redundant_having_wrapper_blockers,
    redundant_subquery_blockers,
)
from ..cte_analysis import analyze_simple_inline_cte


def _normalized_eq(left: str | None, right: str | None) -> bool:
    return normalize_sql(left or "").lower() == normalize_sql(right or "").lower()


class AggregationWrapperFlattenPatchabilityRule:
    rule_id = "AGGREGATION_WRAPPER_FLATTEN_PATCHABLE"

    def evaluate(self, context: CandidatePatchabilityContext) -> CandidatePatchabilityRuleMatch | None:
        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(context.rewritten_sql)

        cte = analyze_simple_inline_cte(original_sql)
        if cte.present and cte.collapsible and normalize_sql(cte.inlined_sql or "") == rewritten_sql:
            return CandidatePatchabilityRuleMatch(
                rule_id=self.rule_id,
                score_delta=20,
                reason="simple CTE inline rewrite is a safe structural patch candidate",
            )

        distinct_match = DISTINCT_WRAPPER_RE.match(original_sql)
        if distinct_match is not None and _normalized_eq(distinct_match.group("outer_select"), distinct_match.group("inner_select")):
            expected = normalize_sql(
                f"SELECT DISTINCT {distinct_match.group('inner_select')} {distinct_match.group('inner_from')} {distinct_match.group('outer_suffix') or ''}"
            )
            if expected == rewritten_sql:
                return CandidatePatchabilityRuleMatch(
                    rule_id=self.rule_id,
                    score_delta=20,
                    reason="redundant DISTINCT wrapper flatten is easy to patch safely",
                )

        having_match = HAVING_WRAPPER_RE.match(original_sql)
        if having_match is not None and _normalized_eq(having_match.group("outer_select"), having_match.group("inner_select")):
            inner_from = str(having_match.group("inner_from") or "")
            expected = normalize_sql(f"SELECT {having_match.group('inner_select')} {inner_from} {having_match.group('outer_suffix') or ''}")
            if not redundant_having_wrapper_blockers(inner_from) and expected == rewritten_sql:
                return CandidatePatchabilityRuleMatch(
                    rule_id=self.rule_id,
                    score_delta=20,
                    reason="redundant HAVING wrapper flatten is easy to patch safely",
                )

        group_by_match = GROUP_BY_WRAPPER_RE.match(original_sql)
        if group_by_match is not None and _normalized_eq(group_by_match.group("outer_select"), group_by_match.group("inner_select")):
            inner_from = str(group_by_match.group("inner_from") or "")
            expected = normalize_sql(f"SELECT {group_by_match.group('inner_select')} {inner_from} {group_by_match.group('outer_suffix') or ''}")
            if not redundant_groupby_wrapper_blockers(inner_from) and expected == rewritten_sql:
                return CandidatePatchabilityRuleMatch(
                    rule_id=self.rule_id,
                    score_delta=20,
                    reason="redundant GROUP BY wrapper flatten is easy to patch safely",
                )

        select_match = SELECT_WRAPPER_RE.match(original_sql)
        if select_match is not None and _normalized_eq(select_match.group("outer_select"), select_match.group("inner_select")):
            inner_from = str(select_match.group("inner_from") or "")
            expected = normalize_sql(f"SELECT {select_match.group('inner_select')} {inner_from}")
            if not redundant_subquery_blockers(inner_from) and expected == rewritten_sql:
                return CandidatePatchabilityRuleMatch(
                    rule_id=self.rule_id,
                    score_delta=15,
                    reason="redundant subquery flatten is structurally easy to patch",
                )
        return None
