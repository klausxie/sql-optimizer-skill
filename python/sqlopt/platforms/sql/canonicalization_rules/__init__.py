from __future__ import annotations

from ..canonicalization_models import RegisteredCanonicalRule
from .alias_only import AliasOnlyCanonicalRule
from .count_form import CountCanonicalRule
from .redundant_subquery import RedundantSubqueryCanonicalRule


def iter_canonical_rules() -> tuple[RegisteredCanonicalRule, ...]:
    return (
        RegisteredCanonicalRule(
            rule_id=CountCanonicalRule.rule_id,
            priority=300,
            implementation=CountCanonicalRule(),
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
