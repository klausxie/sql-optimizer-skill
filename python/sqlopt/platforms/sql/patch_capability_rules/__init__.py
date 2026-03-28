from __future__ import annotations

from ..patchability_models import RegisteredCapabilityRule
from .dynamic_statement_edit import DynamicStatementCanonicalEditCapabilityRule
from .exact_template_edit import ExactTemplateEditCapabilityRule
from .safe_exists_rewrite import SafeExistsRewriteCapabilityRule
from .safe_join_left_to_inner import SafeJoinLeftToInnerCapability
from .safe_union_collapse import SafeUnionCollapseCapabilityRule
from .safe_wrapper_collapse import SafeWrapperCollapseCapabilityRule


def iter_capability_rules() -> tuple[RegisteredCapabilityRule, ...]:
    return (
        RegisteredCapabilityRule(
            capability=SafeJoinLeftToInnerCapability.capability,
            priority=270,
            implementation=SafeJoinLeftToInnerCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeExistsRewriteCapabilityRule.capability,
            priority=260,
            implementation=SafeExistsRewriteCapabilityRule(),
        ),
        RegisteredCapabilityRule(
            capability=SafeUnionCollapseCapabilityRule.capability,
            priority=250,
            implementation=SafeUnionCollapseCapabilityRule(),
        ),
        RegisteredCapabilityRule(
            capability=SafeWrapperCollapseCapabilityRule.capability,
            priority=200,
            implementation=SafeWrapperCollapseCapabilityRule(),
        ),
        RegisteredCapabilityRule(
            capability=DynamicStatementCanonicalEditCapabilityRule.capability,
            priority=150,
            implementation=DynamicStatementCanonicalEditCapabilityRule(),
        ),
        RegisteredCapabilityRule(
            capability=ExactTemplateEditCapabilityRule.capability,
            priority=100,
            implementation=ExactTemplateEditCapabilityRule(),
        ),
    )
