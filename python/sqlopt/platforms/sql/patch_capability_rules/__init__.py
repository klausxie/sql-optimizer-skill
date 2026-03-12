from __future__ import annotations

from ..patchability_models import RegisteredCapabilityRule
from .dynamic_statement_edit import DynamicStatementCanonicalEditCapabilityRule
from .exact_template_edit import ExactTemplateEditCapabilityRule
from .safe_wrapper_collapse import SafeWrapperCollapseCapabilityRule


def iter_capability_rules() -> tuple[RegisteredCapabilityRule, ...]:
    return (
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
