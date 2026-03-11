from __future__ import annotations

from .canonicalization_models import CanonicalAssessment, CanonicalMatch, CanonicalPreferenceSignal, RegisteredCanonicalRule
from .canonicalization_rules import iter_canonical_rules
from .canonicalization_support import build_canonical_context


def _select_primary_match(matches: list[tuple[RegisteredCanonicalRule, CanonicalMatch]]) -> CanonicalMatch:
    primary_binding, primary_match = max(
        matches,
        key=lambda row: (row[0].priority, row[1].score_delta, row[1].rule_id),
    )
    _ = primary_binding
    return primary_match


def assess_candidate_canonicalization_model(original_sql: str, rewritten_sql: str, semantics: dict[str, object]) -> CanonicalAssessment:
    context = build_canonical_context(original_sql, rewritten_sql, semantics)
    if context.row_count_status != "MATCH":
        return CanonicalAssessment.empty()

    matched_rules: list[tuple[RegisteredCanonicalRule, CanonicalMatch]] = []
    for registered_rule in iter_canonical_rules():
        match = registered_rule.implementation.evaluate(context)
        if match is not None:
            matched_rules.append((registered_rule, match))

    if not matched_rules:
        return CanonicalAssessment.empty()

    total_score = sum(row.score_delta for _, row in matched_rules)
    primary = _select_primary_match(matched_rules)
    return CanonicalAssessment(
        preference=CanonicalPreferenceSignal(
            preferred=total_score > 0 and context.normalized_original_sql != context.normalized_rewritten_sql,
            preference_score=total_score,
            primary_rule=primary.rule_id,
            reason=primary.reason,
        ),
        matched_rules=[row for _, row in matched_rules],
    )
