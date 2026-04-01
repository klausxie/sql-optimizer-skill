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

    def test_load_report_inputs_reads_minimal_layout_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report_loader_minimal_") as td:
            run_dir = Path(td)
            (run_dir / "control").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (run_dir / "artifacts" / "scan.jsonl").write_text(
                '{"sqlKey":"pipeline#1","verification":{"sql_key":"pipeline#1","phase":"scan","status":"VERIFIED"}}\n',
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "proposals.jsonl").write_text(
                '{"sqlKey":"pipeline#1","verification":{"sql_key":"pipeline#1","phase":"optimize","status":"VERIFIED"}}\n',
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "acceptance.jsonl").write_text(
                '{"sqlKey":"pipeline#1","verification":{"sql_key":"pipeline#1","phase":"validate","status":"VERIFIED"}}\n',
                encoding="utf-8",
            )
            (run_dir / "artifacts" / "patches.jsonl").write_text(
                '{"statementKey":"pipeline","verification":{"sql_key":"pipeline#1","phase":"patch_generate","status":"VERIFIED"}}\n',
                encoding="utf-8",
            )
            (run_dir / "control" / "manifest.jsonl").write_text(
                '{"stage":"scan","event":"done","payload":{}}\n',
                encoding="utf-8",
            )
            (run_dir / "control" / "state.json").write_text(
                '{"phase_status":{"report":"DONE"},"attempts_by_phase":{"report":2}}',
                encoding="utf-8",
            )

            inputs = load_report_inputs(run_dir)

        self.assertEqual(inputs.units[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.proposals[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.acceptance[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.patches[0]["statementKey"], "pipeline")
        self.assertEqual(inputs.manifest_rows[0].stage, "scan")
        self.assertEqual(len(inputs.verification_rows), 4)
        self.assertEqual(inputs.verification_rows[0]["sql_key"], "pipeline#1")
        self.assertEqual(inputs.state.phase_status["report"], "DONE")
        self.assertEqual(inputs.state.attempts_by_phase["report"], 2)


if __name__ == "__main__":
    unittest.main()
