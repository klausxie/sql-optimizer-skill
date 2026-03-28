from __future__ import annotations

from ..patchability_models import RegisteredCapabilityRule
from .dynamic_statement_edit import DynamicStatementCanonicalEditCapabilityRule
from .exact_template_edit import ExactTemplateEditCapabilityRule
from .safe_distinct_on_simplification import SafeDistinctOnSimplificationCapability
from .safe_exists_rewrite import SafeExistsRewriteCapabilityRule
from .safe_in_list_simplification import SafeInListSimplificationCapability
from .safe_join_consolidation import SafeJoinConsolidationCapability
from .safe_join_elimination import SafeJoinEliminationCapability
from .safe_join_left_to_inner import SafeJoinLeftToInnerCapability
from .safe_join_reordering import SafeJoinReorderingCapability
from .safe_limit_optimization import SafeLimitOptimizationCapability
from .safe_order_by_simplification import SafeOrderBySimplificationCapability
from .safe_subquery_wrapper_collapse import SafeSubqueryWrapperCollapseCapability
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
            capability=SafeJoinEliminationCapability.capability,
            priority=265,
            implementation=SafeJoinEliminationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeJoinReorderingCapability.capability,
            priority=260,
            implementation=SafeJoinReorderingCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeJoinConsolidationCapability.capability,
            priority=255,
            implementation=SafeJoinConsolidationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeUnionCollapseCapabilityRule.capability,
            priority=250,
            implementation=SafeUnionCollapseCapabilityRule(),
        ),
        RegisteredCapabilityRule(
            capability=SafeOrderBySimplificationCapability.capability,
            priority=240,
            implementation=SafeOrderBySimplificationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeLimitOptimizationCapability.capability,
            priority=235,
            implementation=SafeLimitOptimizationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeInListSimplificationCapability.capability,
            priority=230,
            implementation=SafeInListSimplificationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeDistinctOnSimplificationCapability.capability,
            priority=225,
            implementation=SafeDistinctOnSimplificationCapability(),
        ),
        RegisteredCapabilityRule(
            capability=SafeSubqueryWrapperCollapseCapability.capability,
            priority=220,
            implementation=SafeSubqueryWrapperCollapseCapability(),
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
