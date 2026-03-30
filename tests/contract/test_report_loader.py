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

    def test_load_report_inputs_reads_pipeline_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report_loader_pipeline_") as td:
            run_dir = Path(td)
            (run_dir / "pipeline" / "scan").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "optimize").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "validate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "patch_generate").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "verification").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "scan" / "sqlunits.jsonl").write_text('{"sqlKey":"pipeline#1"}\n', encoding="utf-8")
            (run_dir / "pipeline" / "optimize" / "optimization.proposals.jsonl").write_text(
                '{"sqlKey":"pipeline#1"}\n',
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "validate" / "acceptance.results.jsonl").write_text(
                '{"sqlKey":"pipeline#1"}\n',
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl").write_text(
                '{"statementKey":"pipeline"}\n',
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "manifest.jsonl").write_text(
                '{"stage":"scan","event":"done","payload":{}}\n',
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "verification" / "ledger.jsonl").write_text(
                '{"sql_key":"pipeline#1"}\n',
                encoding="utf-8",
            )
            (run_dir / "pipeline" / "supervisor" / "state.json").write_text(
                '{"phase_status":{"report":"DONE"},"attempts_by_phase":{"report":2}}',
                encoding="utf-8",
            )

            inputs = load_report_inputs(run_dir)

        self.assertEqual(inputs.units[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.proposals[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.acceptance[0]["sqlKey"], "pipeline#1")
        self.assertEqual(inputs.patches[0]["statementKey"], "pipeline")
        self.assertEqual(inputs.manifest_rows[0].stage, "scan")
        self.assertEqual(inputs.verification_rows[0]["sql_key"], "pipeline#1")
        self.assertEqual(inputs.state.phase_status["report"], "DONE")
        self.assertEqual(inputs.state.attempts_by_phase["report"], 2)


if __name__ == "__main__":
    unittest.main()
