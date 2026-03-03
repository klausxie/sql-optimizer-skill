from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.stages.report_loader import load_report_inputs


class ReportLoaderTest(unittest.TestCase):
    def test_load_report_inputs_uses_defaults_when_artifacts_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report_loader_") as td:
            run_dir = Path(td)
            inputs = load_report_inputs(run_dir)

        self.assertEqual(inputs.units, [])
        self.assertEqual(inputs.proposals, [])
        self.assertEqual(inputs.acceptance, [])
        self.assertEqual(inputs.patches, [])
        self.assertEqual(inputs.manifest_rows, [])
        self.assertEqual(inputs.verification_rows, [])
        self.assertEqual(inputs.state.phase_status, {})
        self.assertEqual(inputs.state.attempts_by_phase, {})


if __name__ == "__main__":
    unittest.main()
