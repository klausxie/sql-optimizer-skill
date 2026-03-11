from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages import patching_results


class PatchingResultsTest(unittest.TestCase):
    def test_skip_patch_result_includes_optional_apply_fields(self) -> None:
        patch = patching_results.skip_patch_result(
            sql_key="demo.user.find#v1",
            statement_key="demo.user.find",
            reason_code="PATCH_NOT_APPLICABLE",
            reason_message="generated patch cannot apply",
            candidates_evaluated=2,
            selected_candidate_id="c1",
            applicable=False,
            apply_check_error="patch does not apply",
            delivery_outcome={"tier": "MANUAL_REVIEW"},
            repair_hints=[{"hintId": "review-target-drift"}],
            patchability={"applyCheckPassed": False},
            selection_evidence={"acceptanceStatus": "NEED_MORE_PARAMS"},
            fallback_reason_codes=["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"],
        )

        self.assertEqual(patch["selectedCandidateId"], "c1")
        self.assertFalse(patch["applicable"])
        self.assertEqual(patch["applyCheckError"], "patch does not apply")
        self.assertTrue(patch["diffSummary"]["skipped"])
        self.assertEqual(patch["deliveryOutcome"]["tier"], "MANUAL_REVIEW")
        self.assertFalse(patch["patchability"]["applyCheckPassed"])
        self.assertEqual(patch["selectionEvidence"]["acceptanceStatus"], "NEED_MORE_PARAMS")
        self.assertIn("VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", patch["fallbackReasonCodes"])

    def test_selected_patch_result_marks_patch_as_selected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_patch_result_") as td:
            patch_file = Path(td) / "demo.patch"
            patch = patching_results.selected_patch_result(
                sql_key="demo.user.find#v1",
                statement_key="demo.user.find",
                patch_file=patch_file,
                changed_lines=4,
                candidates_evaluated=1,
                selected_candidate_id="c1",
                delivery_outcome={"tier": "READY_TO_APPLY"},
                repair_hints=[],
                patchability={"applyCheckPassed": True},
                selection_evidence={"acceptanceStatus": "PASS"},
                fallback_reason_codes=[],
            )

        self.assertEqual(patch["patchFiles"], [str(patch_file)])
        self.assertEqual(patch["selectionReason"]["code"], "PATCH_SELECTED_SINGLE_PASS")
        self.assertTrue(patch["diffSummary"]["changed"])
        self.assertTrue(patch["applicable"])
        self.assertEqual(patch["deliveryOutcome"]["tier"], "READY_TO_APPLY")
        self.assertEqual(patch["selectionEvidence"]["acceptanceStatus"], "PASS")


if __name__ == "__main__":
    unittest.main()
