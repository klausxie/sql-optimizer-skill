from __future__ import annotations

import unittest

from sqlopt.platforms.sql.patch_safety import assess_patch_safety_model
from sqlopt.platforms.sql.rewrite_facts_models import RewriteFacts, SemanticRewriteFacts, WrapperQueryRewriteFacts


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


if __name__ == "__main__":
    unittest.main()
