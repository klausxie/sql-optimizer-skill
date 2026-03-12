from __future__ import annotations

from .template_rendering import normalize_sql_text
from .dynamic_candidate_intent_models import DynamicCandidateIntentAssessment, DynamicCandidateIntentMatch
from .dynamic_candidate_intent_rules import iter_dynamic_candidate_intent_rules


def assess_dynamic_candidate_intent_model(
    sql_unit: dict[str, object],
    original_sql: str,
    rewritten_sql: str,
    rewrite_facts,
) -> DynamicCandidateIntentAssessment:
    dynamic_profile = rewrite_facts.dynamic_template.capability_profile
    matches: list[DynamicCandidateIntentMatch] = []
    for registered_rule in iter_dynamic_candidate_intent_rules():
        match = registered_rule.implementation.evaluate(sql_unit, original_sql, rewritten_sql, rewrite_facts)
        matches.append(match)

    matched = [row for row in matches if row.matched]
    if matched:
        primary = matched[0]
        rebuilt_template = str(primary.rebuilt_template or "").strip() or None
        template_sql = str(sql_unit.get("templateSql") or "").strip()
        template_effective_change = bool(
            rebuilt_template and normalize_sql_text(rebuilt_template) != normalize_sql_text(template_sql)
        )
        return DynamicCandidateIntentAssessment(
            intent=str(primary.intent or "UNSAFE_DYNAMIC_REWRITE"),
            template_preserving=str(primary.intent or "") == "TEMPLATE_PRESERVING_STATEMENT_EDIT",
            blocking_reason=primary.blocking_reason,
            primary_rule=primary.rule_id,
            rebuilt_template=rebuilt_template,
            template_effective_change=template_effective_change or bool(primary.template_effective_change),
            matches=matches,
        )

    if dynamic_profile.capability_tier not in {"", "NONE", "SAFE_BASELINE"}:
        blocker = str(dynamic_profile.blocker_family or "DYNAMIC_TEMPLATE_REVIEW_REQUIRED")
        return DynamicCandidateIntentAssessment(
            intent="UNSAFE_DYNAMIC_REWRITE",
            template_preserving=False,
            blocking_reason=blocker,
            primary_rule=None,
            rebuilt_template=None,
            template_effective_change=False,
            matches=matches,
        )
    if normalize_sql_text(original_sql) == normalize_sql_text(rewritten_sql):
        return DynamicCandidateIntentAssessment(
            intent="NO_EFFECTIVE_TEMPLATE_CHANGE",
            template_preserving=False,
            blocking_reason="NO_EFFECTIVE_TEMPLATE_CHANGE",
            primary_rule=None,
            rebuilt_template=None,
            template_effective_change=False,
            matches=matches,
        )
    return DynamicCandidateIntentAssessment(
        intent="UNSAFE_DYNAMIC_REWRITE",
        template_preserving=False,
        blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
        primary_rule=None,
        rebuilt_template=None,
        template_effective_change=False,
        matches=matches,
    )


def assess_dynamic_candidate_intent(
    sql_unit: dict[str, object],
    original_sql: str,
    rewritten_sql: str,
    rewrite_facts,
) -> dict[str, object]:
    return assess_dynamic_candidate_intent_model(sql_unit, original_sql, rewritten_sql, rewrite_facts).to_dict()
