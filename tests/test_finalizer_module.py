from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.application.finalizer import RunFinalizer
from sqlopt.contracts import ContractValidator
from sqlopt.errors import StageError

ROOT = Path(__file__).resolve().parents[1]


class _RepoStub:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.saved_state: dict = {}
        self.meta_statuses: list[str] = []
        self.step_results: list[tuple[str, str]] = []

    def save_state(self, state: dict) -> None:
        self.saved_state = dict(state)

    def set_meta_status(self, status: str) -> None:
        self.meta_statuses.append(status)

    def append_step_result(self, phase: str, status: str, **_kwargs) -> None:
        self.step_results.append((phase, status))


class FinalizerModuleTest(unittest.TestCase):
    def _base_state(self) -> dict:
        return {
            "current_phase": "patch_generate",
            "phase_status": {
                "preflight": "DONE",
                "scan": "DONE",
                "optimize": "DONE",
                "validate": "DONE",
                "patch_generate": "DONE",
                "report": "PENDING",
            },
            "attempts_by_phase": {"report": 0},
            "report_rebuild_required": False,
            "last_error": None,
            "last_reason_code": None,
        }

    def test_finalize_report_success_updates_attempts_and_meta(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_finalizer_ok_") as td:
            run_dir = Path(td)
            repo = _RepoStub(run_dir)
            finalizer = RunFinalizer(
                report_enabled=lambda _cfg: True,
                report_generate=lambda _run_id, _mode, _cfg, _dir, _validator: None,
            )
            state = self._base_state()
            ok = finalizer.finalize_report_if_enabled(
                run_dir,
                {"report": {"enabled": True}},
                ContractValidator(ROOT),
                state,
                final_meta_status="COMPLETED",
                repository=repo,  # type: ignore[arg-type]
                run_phase_action_fn=lambda _cfg, _phase, fn: (fn(), 2),
                record_failure_fn=lambda *_args, **_kwargs: None,
            )

        self.assertTrue(ok)
        self.assertEqual(state["attempts_by_phase"]["report"], 2)
        self.assertEqual(repo.meta_statuses, ["COMPLETED"])
        self.assertIn(("report", "DONE"), repo.step_results)

    def test_finalize_report_failure_marks_ready_to_finalize_on_completed_rebuild(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_finalizer_fail_") as td:
            run_dir = Path(td)
            repo = _RepoStub(run_dir)
            state = self._base_state()
            finalizer = RunFinalizer(
                report_enabled=lambda _cfg: True,
                report_generate=lambda _run_id, _mode, _cfg, _dir, _validator: None,
            )
            ok = finalizer.finalize_report_if_enabled(
                run_dir,
                {"report": {"enabled": True}},
                ContractValidator(ROOT),
                state,
                final_meta_status="COMPLETED",
                repository=repo,  # type: ignore[arg-type]
                run_phase_action_fn=lambda _cfg, _phase, _fn: (_ for _ in ()).throw(
                    StageError("report failed", reason_code="REPORT_FAILED")
                ),
                record_failure_fn=lambda *_args, **_kwargs: None,
            )

        self.assertFalse(ok)
        self.assertEqual(repo.meta_statuses, ["READY_TO_FINALIZE"])


if __name__ == "__main__":
    unittest.main()
