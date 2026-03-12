from __future__ import annotations

from ..dynamic_candidate_intent_models import RegisteredDynamicCandidateIntentRule
from .dynamic_filter_from_alias_cleanup import DynamicFilterFromAliasCleanupIntentRule
from .dynamic_filter_select_list_cleanup import DynamicFilterSelectListCleanupIntentRule
from .dynamic_filter_wrapper import DynamicFilterWrapperIntentRule
from .dynamic_count_wrapper import DynamicCountWrapperIntentRule
from .static_include_statement import StaticIncludeStatementIntentRule


def iter_dynamic_candidate_intent_rules() -> tuple[RegisteredDynamicCandidateIntentRule, ...]:
    return (
        RegisteredDynamicCandidateIntentRule(
            rule_id=DynamicFilterFromAliasCleanupIntentRule.rule_id,
            priority=225,
            implementation=DynamicFilterFromAliasCleanupIntentRule(),
        ),
        RegisteredDynamicCandidateIntentRule(
            rule_id=DynamicFilterSelectListCleanupIntentRule.rule_id,
            priority=200,
            implementation=DynamicFilterSelectListCleanupIntentRule(),
        ),
        RegisteredDynamicCandidateIntentRule(
            rule_id=DynamicFilterWrapperIntentRule.rule_id,
            priority=175,
            implementation=DynamicFilterWrapperIntentRule(),
        ),
        RegisteredDynamicCandidateIntentRule(
            rule_id=DynamicCountWrapperIntentRule.rule_id,
            priority=150,
            implementation=DynamicCountWrapperIntentRule(),
        ),
        RegisteredDynamicCandidateIntentRule(
            rule_id=StaticIncludeStatementIntentRule.rule_id,
            priority=100,
            implementation=StaticIncludeStatementIntentRule(),
        ),
    )
