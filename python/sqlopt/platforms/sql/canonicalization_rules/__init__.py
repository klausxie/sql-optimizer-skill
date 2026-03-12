from __future__ import annotations

from ..canonicalization_models import RegisteredCanonicalRule
from .alias_only import AliasOnlyCanonicalRule
from .count_form import CountCanonicalRule
from .redundant_distinct import RedundantDistinctCanonicalRule
from .redundant_groupby import RedundantGroupByCanonicalRule
from .redundant_having import RedundantHavingCanonicalRule
from .redundant_subquery import RedundantSubqueryCanonicalRule


def iter_canonical_rules() -> tuple[RegisteredCanonicalRule, ...]:
    return (
        RegisteredCanonicalRule(
            rule_id=CountCanonicalRule.rule_id,
            priority=300,
            implementation=CountCanonicalRule(),
        ),
        RegisteredCanonicalRule(
            rule_id=RedundantDistinctCanonicalRule.rule_id,
            priority=250,
            implementation=RedundantDistinctCanonicalRule(),
        ),
        RegisteredCanonicalRule(
            rule_id=RedundantGroupByCanonicalRule.rule_id,
            priority=225,
            implementation=RedundantGroupByCanonicalRule(),
        ),
        RegisteredCanonicalRule(
            rule_id=RedundantHavingCanonicalRule.rule_id,
            priority=220,
            implementation=RedundantHavingCanonicalRule(),
        ),
        RegisteredCanonicalRule(
            rule_id=RedundantSubqueryCanonicalRule.rule_id,
            priority=200,
            implementation=RedundantSubqueryCanonicalRule(),
        ),
        RegisteredCanonicalRule(
            rule_id=AliasOnlyCanonicalRule.rule_id,
            priority=100,
            implementation=AliasOnlyCanonicalRule(),
        ),
    )
