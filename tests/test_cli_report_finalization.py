from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.cli import _advance_one_step, _finalize_report_if_enabled
from sqlopt.contracts import ContractValidator
from sqlopt.supervisor import init_run, load_state, save_state

ROOT = Path(__file__).resolve().parents[1]


class CliReportFinalizationTest(unittest.TestCase):
    def _prepare_completed_run(self, run_dir: Path) -> None:
        init_run(run_dir, {"config_version": "v1"}, "run_test")
        (run_dir / "scan.sqlunits.jsonl").write_text("", encoding="utf-8")
        (run_dir / "proposals" / "optimization.proposals.jsonl").write_text("", encoding="utf-8")
        (run_dir / "acceptance" / "acceptance.results.jsonl").write_text("", encoding="utf-8")
        (run_dir / "patches" / "patch.results.jsonl").write_text("", encoding="utf-8")
        state = load_state(run_dir)
        state["current_phase"] = "report"
        state["phase_status"] = {
            "preflight": "DONE",
            "scan": "DONE",
            "optimize": "DONE",
            "validate": "DONE",
            "patch_generate": "DONE",
            "report": "DONE",
        }
        save_state(run_dir, state)

    def test_finalize_report_regenerates_even_when_report_is_done(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_report_final_") as td:
            run_dir = Path(td)
            self._prepare_completed_run(run_dir)
            state = load_state(run_dir)
            with patch("sqlopt.cli._run_phase_action", return_value=({}, 1)) as mock_run:
                _finalize_report_if_enabled(
                    run_dir,
                    {"report": {"enabled": True}},
                    ContractValidator(ROOT),
                    state,
                    final_meta_status="COMPLETED",
                )

            self.assertEqual(mock_run.call_count, 1)
            self.assertEqual(load_state(run_dir)["attempts_by_phase"]["report"], 1)

    def test_advance_to_report_always_finalizes_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cli_report_stage_") as td:
            run_dir = Path(td)
            self._prepare_completed_run(run_dir)
            config = {"report": {"enabled": True}, "validate": {}}
            with patch("sqlopt.cli._finalize_report_if_enabled") as mock_finalize:
                result = _advance_one_step(run_dir, config, "report", ContractValidator(ROOT))

            self.assertEqual(result, {"complete": True, "phase": "report"})
            self.assertEqual(mock_finalize.call_count, 1)


if __name__ == "__main__":
    unittest.main()
