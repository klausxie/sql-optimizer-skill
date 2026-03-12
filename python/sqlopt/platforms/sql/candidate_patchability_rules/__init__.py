from __future__ import annotations

from ..candidate_patchability_models import RegisteredCandidatePatchabilityRule
from .aggregation_speculative import AggregationSpeculativePenaltyRule
from .aggregation_wrapper import AggregationWrapperFlattenPatchabilityRule
from .generic_placeholder import GenericPlaceholderPenaltyRule
from .join_heavy import JoinHeavyPenaltyRule
from .mybatis_placeholder import MyBatisPlaceholderPreservedRule
from .ordering_rewrite import OrderingRewritePatchabilityRule
from .projection_rewrite import ProjectionRewritePatchabilityRule
from .rule_source import RuleSourcePatchabilityRule


def iter_candidate_patchability_rules() -> tuple[RegisteredCandidatePatchabilityRule, ...]:
    return (
        RegisteredCandidatePatchabilityRule(
            rule_id=RuleSourcePatchabilityRule.rule_id,
            priority=600,
            implementation=RuleSourcePatchabilityRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=ProjectionRewritePatchabilityRule.rule_id,
            priority=500,
            implementation=ProjectionRewritePatchabilityRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=AggregationWrapperFlattenPatchabilityRule.rule_id,
            priority=450,
            implementation=AggregationWrapperFlattenPatchabilityRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=OrderingRewritePatchabilityRule.rule_id,
            priority=400,
            implementation=OrderingRewritePatchabilityRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=MyBatisPlaceholderPreservedRule.rule_id,
            priority=300,
            implementation=MyBatisPlaceholderPreservedRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=JoinHeavyPenaltyRule.rule_id,
            priority=200,
            implementation=JoinHeavyPenaltyRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=AggregationSpeculativePenaltyRule.rule_id,
            priority=150,
            implementation=AggregationSpeculativePenaltyRule(),
        ),
        RegisteredCandidatePatchabilityRule(
            rule_id=GenericPlaceholderPenaltyRule.rule_id,
            priority=100,
            implementation=GenericPlaceholderPenaltyRule(),
        ),
    )
