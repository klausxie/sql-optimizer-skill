from __future__ import annotations

import unittest

from sqlopt.platforms.sql.patch_safety import assess_patch_safety_model
from sqlopt.platforms.sql.rewrite_facts_models import (
    AggregationCapabilityProfile,
    AggregationQueryRewriteFacts,
    DynamicTemplateCapabilityProfile,
    DynamicTemplateRewriteFacts,
    RewriteFacts,
    SemanticRewriteFacts,
    WrapperQueryRewriteFacts,
)


class PatchSafetyTest(unittest.TestCase):
    def test_capability_assessment_orders_allowed_capabilities_by_priority(self) -> None:
        assessment = assess_patch_safety_model(
            {
                "effectiveChange": True,
                "semantic": {
                    "status": "PASS",
                    "confidence": "HIGH",
                    "fingerprintStrength": "EXACT",
                    "hardConflicts": [],
                },
                "wrapperQuery": {
                    "present": True,
                    "collapsible": True,
                    "collapseCandidate": True,
                    "blockers": [],
                },
            }
        )

        self.assertTrue(assessment.eligible)
        self.assertEqual(
            assessment.allowed_capabilities,
            ["SAFE_WRAPPER_COLLAPSE", "EXACT_TEMPLATE_EDIT"],
        )
        self.assertEqual(assessment.blocking_reasons, [])

    def test_capability_assessment_accepts_typed_rewrite_facts(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                dynamic_features=["INCLUDE"],
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                wrapper_query=WrapperQueryRewriteFacts(
                    present=True,
                    aggregate="COUNT",
                    static_include_tree=True,
                    inner_sql="SELECT id FROM users",
                    inner_from_suffix="FROM users",
                    collapsible=True,
                    collapse_candidate=True,
                    blockers=[],
                    rewritten_count_expr="*",
                    rewritten_from_suffix="FROM users",
                ),
            )
        )

        self.assertTrue(assessment.eligible)
        self.assertEqual(assessment.blocking_reason, None)

    def test_aggregation_review_required_blocks_exact_template_edit(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                aggregation_query=AggregationQueryRewriteFacts(
                    present=True,
                    distinct_present=True,
                    group_by_present=False,
                    having_present=False,
                    window_present=False,
                    union_present=False,
                    distinct_relaxation_candidate=True,
                    blockers=["DISTINCT_PRESENT"],
                    capability_profile=AggregationCapabilityProfile(
                        shape_family="DISTINCT",
                        capability_tier="REVIEW_REQUIRED",
                        constraint_family="DISTINCT_RELAXATION",
                        safe_baseline_family=None,
                        wrapper_flatten_candidate=False,
                        direct_relaxation_candidate=True,
                        blockers=["DISTINCT_PRESENT"],
                    ),
                ),
            ),
            {
                "intent": "TEMPLATE_PRESERVING_STATEMENT_EDIT",
                "templatePreserving": True,
                "blockingReason": None,
            },
        )

        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.allowed_capabilities, [])
        self.assertEqual(assessment.blocking_reason, "AGGREGATION_CONSTRAINT:DISTINCT_RELAXATION")
        self.assertIn("AGGREGATION_CONSTRAINT:DISTINCT_RELAXATION", assessment.blocking_reasons)
        self.assertEqual(assessment.aggregation_constraint_family, "DISTINCT_RELAXATION")
        self.assertEqual(assessment.aggregation_capability_tier, "REVIEW_REQUIRED")
        self.assertIsNone(assessment.aggregation_safe_baseline_family)

    def test_aggregation_safe_baseline_does_not_block_exact_template_edit(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                aggregation_query=AggregationQueryRewriteFacts(
                    present=True,
                    distinct_present=False,
                    group_by_present=True,
                    having_present=True,
                    window_present=False,
                    union_present=False,
                    distinct_relaxation_candidate=False,
                    blockers=["GROUP_BY_PRESENT", "HAVING_PRESENT"],
                    capability_profile=AggregationCapabilityProfile(
                        shape_family="HAVING",
                        capability_tier="SAFE_BASELINE",
                        constraint_family="SAFE_BASELINE",
                        safe_baseline_family="REDUNDANT_HAVING_WRAPPER",
                        wrapper_flatten_candidate=True,
                        direct_relaxation_candidate=False,
                        blockers=["GROUP_BY_PRESENT", "HAVING_PRESENT"],
                    ),
                ),
            )
        )

        self.assertTrue(assessment.eligible)
        self.assertIn("EXACT_TEMPLATE_EDIT", assessment.allowed_capabilities)
        self.assertEqual(assessment.aggregation_constraint_family, "SAFE_BASELINE")
        self.assertEqual(assessment.aggregation_capability_tier, "SAFE_BASELINE")
        self.assertEqual(assessment.aggregation_safe_baseline_family, "REDUNDANT_HAVING_WRAPPER")

    def test_dynamic_static_include_safe_baseline_exposes_dynamic_capability(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                dynamic_features=["INCLUDE"],
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                dynamic_template=DynamicTemplateRewriteFacts(
                    present=True,
                    statement_features=["INCLUDE"],
                    include_fragment_refs=["demo.user.AdvancedUserColumns"],
                    include_dynamic_subtree=False,
                    include_property_bindings=False,
                    capability_profile=DynamicTemplateCapabilityProfile(
                        shape_family="STATIC_INCLUDE_ONLY",
                        capability_tier="SAFE_BASELINE",
                        patch_surface="STATEMENT_BODY",
                        blocker_family=None,
                        template_preserving_candidate=True,
                        blockers=[],
                    ),
                ),
            ),
            {
                "intent": "TEMPLATE_PRESERVING_STATEMENT_EDIT",
                "templatePreserving": True,
                "blockingReason": None,
            },
        )

        self.assertTrue(assessment.eligible)
        self.assertIn("DYNAMIC_STATEMENT_CANONICAL_EDIT", assessment.allowed_capabilities)
        self.assertEqual(assessment.dynamic_shape_family, "STATIC_INCLUDE_ONLY")
        self.assertEqual(assessment.dynamic_capability_tier, "SAFE_BASELINE")
        self.assertEqual(assessment.dynamic_patch_surface, "STATEMENT_BODY")
        self.assertIsNone(assessment.dynamic_blocking_reason)

    def test_dynamic_foreach_shape_blocks_exact_template_edit(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                dynamic_features=["INCLUDE", "WHERE", "FOREACH"],
                template_anchor_stable=False,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                dynamic_template=DynamicTemplateRewriteFacts(
                    present=True,
                    statement_features=["INCLUDE", "WHERE", "FOREACH"],
                    include_fragment_refs=["demo.order.OrderColumns"],
                    include_dynamic_subtree=False,
                    include_property_bindings=False,
                    capability_profile=DynamicTemplateCapabilityProfile(
                        shape_family="FOREACH_IN_PREDICATE",
                        capability_tier="REVIEW_REQUIRED",
                        patch_surface="WHERE_CLAUSE",
                        blocker_family="FOREACH_INCLUDE_PREDICATE",
                        template_preserving_candidate=False,
                        blockers=["FOREACH_INCLUDE_PREDICATE"],
                    ),
                ),
            ),
            {
                "intent": "UNSAFE_DYNAMIC_REWRITE",
                "templatePreserving": False,
                "blockingReason": "FOREACH_INCLUDE_PREDICATE",
            },
        )

        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.blocking_reason, "DYNAMIC_TEMPLATE:FOREACH_INCLUDE_PREDICATE")
        self.assertEqual(assessment.dynamic_shape_family, "FOREACH_IN_PREDICATE")
        self.assertEqual(assessment.dynamic_capability_tier, "REVIEW_REQUIRED")
        self.assertEqual(assessment.dynamic_blocking_reason, "FOREACH_INCLUDE_PREDICATE")

    def test_dynamic_static_include_no_effective_diff_exposes_specific_blocker(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=False,
                dynamic_features=["INCLUDE"],
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                dynamic_template=DynamicTemplateRewriteFacts(
                    present=True,
                    statement_features=["INCLUDE"],
                    include_fragment_refs=["demo.user.AdvancedUserColumns"],
                    include_dynamic_subtree=False,
                    include_property_bindings=False,
                    capability_profile=DynamicTemplateCapabilityProfile(
                        shape_family="STATIC_INCLUDE_ONLY",
                        capability_tier="SAFE_BASELINE",
                        patch_surface="STATEMENT_BODY",
                        blocker_family=None,
                        template_preserving_candidate=True,
                        blockers=[],
                    ),
                ),
            ),
            {
                "intent": "TEMPLATE_PRESERVING_STATEMENT_EDIT",
                "templatePreserving": True,
                "blockingReason": None,
                "templateEffectiveChange": False,
            },
        )

        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.blocking_reason, "PATCH_NO_EFFECTIVE_CHANGE")
        self.assertEqual(assessment.dynamic_blocking_reason, "STATIC_INCLUDE_NO_EFFECTIVE_DIFF")

    def test_dynamic_filter_no_effective_diff_exposes_specific_blocker(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=False,
                dynamic_features=["WHERE", "IF"],
                template_anchor_stable=False,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                dynamic_template=DynamicTemplateRewriteFacts(
                    present=True,
                    statement_features=["WHERE", "IF"],
                    include_fragment_refs=[],
                    include_dynamic_subtree=False,
                    include_property_bindings=False,
                    capability_profile=DynamicTemplateCapabilityProfile(
                        shape_family="IF_GUARDED_FILTER_STATEMENT",
                        capability_tier="REVIEW_REQUIRED",
                        patch_surface="WHERE_CLAUSE",
                        blocker_family="DYNAMIC_FILTER_SUBTREE",
                        template_preserving_candidate=False,
                        blockers=["DYNAMIC_FILTER_SUBTREE"],
                    ),
                ),
            ),
            {
                "intent": "NO_EFFECTIVE_TEMPLATE_CHANGE",
                "templatePreserving": False,
                "blockingReason": "NO_EFFECTIVE_TEMPLATE_CHANGE",
                "templateEffectiveChange": False,
            },
        )

        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.blocking_reason, "PATCH_NO_EFFECTIVE_CHANGE")
        self.assertEqual(assessment.dynamic_blocking_reason, "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF")

    def test_dynamic_static_include_with_property_bindings_uses_fragment_dependent_blocker(self) -> None:
        assessment = assess_patch_safety_model(
            RewriteFacts(
                effective_change=True,
                dynamic_features=["INCLUDE"],
                template_anchor_stable=True,
                semantic=SemanticRewriteFacts(
                    status="PASS",
                    confidence="HIGH",
                    evidence_level="DB_FINGERPRINT",
                    fingerprint_strength="EXACT",
                    hard_conflicts=[],
                ),
                dynamic_template=DynamicTemplateRewriteFacts(
                    present=True,
                    statement_features=["INCLUDE"],
                    include_fragment_refs=["demo.user.AdvancedUserColumns"],
                    include_dynamic_subtree=False,
                    include_property_bindings=True,
                    capability_profile=DynamicTemplateCapabilityProfile(
                        shape_family="STATIC_INCLUDE_ONLY",
                        capability_tier="REVIEW_REQUIRED",
                        patch_surface="STATEMENT_BODY",
                        blocker_family="STATIC_INCLUDE_FRAGMENT_DEPENDENT",
                        template_preserving_candidate=False,
                        blockers=["STATIC_INCLUDE_FRAGMENT_DEPENDENT"],
                    ),
                ),
            ),
        )

        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.dynamic_blocking_reason, "STATIC_INCLUDE_FRAGMENT_DEPENDENT")


if __name__ == "__main__":
    unittest.main()
