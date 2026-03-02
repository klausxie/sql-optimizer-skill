from __future__ import annotations

import unittest

from sqlopt.failure_classification import classify_reason_code


class FailureClassificationTest(unittest.TestCase):
    def test_phase_mapping_takes_effect(self) -> None:
        self.assertEqual(classify_reason_code("VALIDATE_DB_UNREACHABLE", phase="validate"), "degradable")
        self.assertEqual(classify_reason_code("VALIDATE_EQUIVALENCE_MISMATCH", phase="validate"), "fatal")
        self.assertEqual(classify_reason_code("RUNTIME_STAGE_TIMEOUT", phase="scan"), "retryable")
        self.assertEqual(classify_reason_code("SCAN_CLASS_NOT_FOUND", phase="scan"), "degradable")
        self.assertEqual(classify_reason_code("SCAN_TYPE_ATTR_SANITIZED", phase="scan"), "degradable")
        self.assertEqual(classify_reason_code("SCAN_STATEMENT_PARSE_DEGRADED", phase="scan"), "degradable")
        self.assertEqual(classify_reason_code("SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD", phase="scan"), "fatal")
        self.assertEqual(classify_reason_code("UNKNOWN_CODE", phase="validate"), "fatal")


if __name__ == "__main__":
    unittest.main()
