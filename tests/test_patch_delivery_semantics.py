from __future__ import annotations

import unittest

from sqlopt.stages.patch_applicability import PatchApplicabilityResult, build_delivery_verdict


class PatchDeliverySemanticsTest(unittest.TestCase):
    def test_statement_artifact_apply_ready_requires_applicability_and_proof(self) -> None:
        applicability = PatchApplicabilityResult(
            artifact_kind="STATEMENT",
            target_file="/tmp/demo_mapper.xml",
            materialized=True,
            applicability_checked=True,
            apply_ready_candidate=True,
            failure_class=None,
            reason_code=None,
        )

        verdict = build_delivery_verdict(applicability=applicability, proof_ok=True, proof_reason_code=None)

        self.assertEqual(verdict["artifactKind"], "STATEMENT")
        self.assertEqual(verdict["deliveryStage"], "APPLY_READY")
        self.assertIsNone(verdict["failureClass"])

    def test_fragment_artifact_applicability_failure_is_not_proof_failure(self) -> None:
        applicability = PatchApplicabilityResult(
            artifact_kind="FRAGMENT",
            target_file="/tmp/demo_mapper.xml",
            materialized=True,
            applicability_checked=False,
            apply_ready_candidate=False,
            failure_class="APPLICABILITY_FAILURE",
            reason_code="PATCH_ARTIFACT_TARGET_MISMATCH",
        )

        verdict = build_delivery_verdict(
            applicability=applicability,
            proof_ok=False,
            proof_reason_code="PATCH_TARGET_DRIFT",
        )

        self.assertEqual(verdict["artifactKind"], "FRAGMENT")
        self.assertEqual(verdict["deliveryStage"], "APPLICABILITY_FAILED")
        self.assertEqual(verdict["failureClass"], "APPLICABILITY_FAILURE")
        self.assertEqual(verdict["reasonCode"], "PATCH_ARTIFACT_TARGET_MISMATCH")

    def test_template_artifact_proof_failure_after_applicability_check_is_not_apply_ready(self) -> None:
        applicability = PatchApplicabilityResult(
            artifact_kind="TEMPLATE",
            target_file="/tmp/demo_mapper.xml",
            materialized=True,
            applicability_checked=True,
            apply_ready_candidate=True,
            failure_class=None,
            reason_code=None,
        )

        verdict = build_delivery_verdict(
            applicability=applicability,
            proof_ok=False,
            proof_reason_code="PATCH_XML_PARSE_FAILED",
        )

        self.assertEqual(verdict["artifactKind"], "TEMPLATE")
        self.assertEqual(verdict["deliveryStage"], "PROOF_FAILED")
        self.assertEqual(verdict["failureClass"], "PROOF_FAILURE")
        self.assertEqual(verdict["reasonCode"], "PATCH_XML_PARSE_FAILED")


if __name__ == "__main__":
    unittest.main()
