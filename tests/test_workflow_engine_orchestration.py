from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlopt.application import workflow_engine
from sqlopt.contracts import ContractValidator
from sqlopt.errors import StageError

ROOT = Path(__file__).resolve().parents[1]


class _FakeRepository:
    def __init__(self, run_dir: Path, state: dict, plan: dict):
        self.run_dir = run_dir
        self.state = state
        self.plan = plan
        self.saved_states: list[dict] = []
        self.saved_plans: list[dict] = []
        self.step_results: list[tuple[str, str, dict]] = []
        self.meta_statuses: list[str] = []

    def load_state(self) -> dict:
        return self.state

    def save_state(self, state: dict) -> None:
        self.state = state
        self.saved_states.append(
            {
                "current_phase": state.get("current_phase"),
                "phase_status": dict(state.get("phase_status", {})),
                "attempts_by_phase": dict(state.get("attempts_by_phase", {})),
            }
        )

    def get_plan(self) -> dict:
        return self.plan

    def set_plan(self, plan: dict) -> None:
        self.plan = plan
        self.saved_plans.append(dict(plan))

    def append_step_result(self, phase: str, status: str, **kwargs) -> None:
        self.step_results.append((phase, status, kwargs))

    def set_meta_status(self, status: str) -> None:
        self.meta_statuses.append(status)


class _DummyProgress:
    def report_phase_start(self, phase: str, message: str) -> None:
        pass

    def report_phase_complete(self, phase: str) -> None:
        pass

    def report_info(self, message: str) -> None:
        pass

    def report_statement_progress(self, current_index: int, total_statements: int, key: str) -> None:
        pass


def _initial_state() -> dict:
    return {
        "current_phase": "preflight",
        "phase_status": {
            "preflight": "PENDING",
            "scan": "PENDING",
            "optimize": "PENDING",
            "validate": "PENDING",
            "patch_generate": "PENDING",
            "report": "PENDING",
        },
        "statements": {},
        "attempts_by_phase": {
            "preflight": 0,
            "scan": 0,
            "optimize": 0,
            "validate": 0,
            "patch_generate": 0,
            "report": 0,
        },
        "last_error": None,
        "last_reason_code": None,
        "updated_at": "2026-03-02T00:00:00+00:00",
    }


class WorkflowEngineOrchestrationTest(unittest.TestCase):
    def _validator(self) -> ContractValidator:
        return ContractValidator(ROOT)

    def test_finalize_report_success_updates_state_and_meta(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_report_ok_") as td:
            run_dir = Path(td)
            state = _initial_state()
            repo = _FakeRepository(run_dir, state, {"sql_keys": []})

            workflow_engine.finalize_report_if_enabled(
                run_dir,
                {"report": {"enabled": True}},
                self._validator(),
                state,
                final_meta_status="COMPLETED",
                repository=repo,
                run_phase_action_fn=lambda config, phase, fn: ({}, 2),
            )

        self.assertEqual(state["phase_status"]["report"], "DONE")
        self.assertEqual(state["current_phase"], "report")
        self.assertEqual(state["attempts_by_phase"]["report"], 2)
        self.assertEqual(repo.meta_statuses, ["COMPLETED"])
        self.assertEqual(repo.step_results[0][0:2], ("report", "DONE"))

    def test_finalize_report_failure_delegates_to_record_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_report_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            repo = _FakeRepository(run_dir, state, {"sql_keys": []})
            record_failure = Mock()

            workflow_engine.finalize_report_if_enabled(
                run_dir,
                {"report": {"enabled": True}},
                self._validator(),
                state,
                final_meta_status="FAILED",
                repository=repo,
                run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                    StageError("report failed", reason_code="REPORT_FAILED")
                ),
                record_failure_fn=record_failure,
            )

        record_failure.assert_called_once()
        self.assertEqual(record_failure.call_args.args[2], "report")
        self.assertEqual(repo.meta_statuses, [])

    def test_advance_preflight_failure_without_report_sets_failed_meta(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_preflight_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            repo = _FakeRepository(run_dir, state, {"sql_keys": []})
            record_failure = Mock()
            finalize_report = Mock()

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with self.assertRaises(StageError):
                    workflow_engine.advance_one_step(
                        run_dir,
                        {"report": {"enabled": False}, "validate": {}},
                        "patch_generate",
                        self._validator(),
                        repository=repo,
                        run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                            StageError("preflight failed", reason_code="PREFLIGHT_FAILED")
                        ),
                        record_failure_fn=record_failure,
                        finalize_report_if_enabled_fn=finalize_report,
                    )

        record_failure.assert_called_once()
        self.assertEqual(record_failure.call_args.args[2], "preflight")
        finalize_report.assert_not_called()
        self.assertEqual(repo.meta_statuses, ["FAILED"])

    def test_advance_preflight_to_stage_without_report_finalizes_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_preflight_done_") as td:
            run_dir = Path(td)
            state = _initial_state()
            repo = _FakeRepository(run_dir, state, {"sql_keys": []})
            finalize_without_report = Mock()

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                result = workflow_engine.advance_one_step(
                    run_dir,
                    {"report": {"enabled": False}, "validate": {}},
                    "preflight",
                    self._validator(),
                    repository=repo,
                    run_phase_action_fn=lambda config, phase, fn: ({}, 1),
                    finalize_without_report_fn=finalize_without_report,
                )

        self.assertEqual(result, {"complete": True, "phase": "preflight"})
        self.assertEqual(state["phase_status"]["preflight"], "DONE")
        self.assertEqual(state["attempts_by_phase"]["preflight"], 1)
        finalize_without_report.assert_called_once()
        self.assertEqual(finalize_without_report.call_args.kwargs["final_meta_status"], "COMPLETED")
        self.assertEqual(repo.step_results[0][0:2], ("preflight", "DONE"))

    def test_advance_optimize_completion_marks_downstream_skipped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_opt_done_") as td:
            run_dir = Path(td)
            state = _initial_state()
            state["current_phase"] = "optimize"
            state["phase_status"]["preflight"] = "DONE"
            state["phase_status"]["scan"] = "DONE"
            state["statements"] = {"demo.user.find#v1": {"optimize": "DONE", "validate": "PENDING", "patch_generate": "PENDING"}}
            repo = _FakeRepository(run_dir, state, {"sql_keys": ["demo.user.find#v1"]})
            finalize_without_report = Mock()

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with patch("sqlopt.application.workflow_engine.load_index", return_value=({}, {}, {})):
                    result = workflow_engine.advance_one_step(
                        run_dir,
                        {"report": {"enabled": False}, "validate": {}},
                        "optimize",
                        self._validator(),
                        repository=repo,
                        finalize_without_report_fn=finalize_without_report,
                    )

        self.assertEqual(result, {"complete": True, "phase": "optimize"})
        self.assertEqual(state["phase_status"]["optimize"], "DONE")
        self.assertEqual(state["phase_status"]["validate"], "SKIPPED")
        self.assertEqual(state["phase_status"]["patch_generate"], "SKIPPED")
        finalize_without_report.assert_called_once()
        self.assertEqual(finalize_without_report.call_args.kwargs["final_meta_status"], "COMPLETED")

    def test_advance_scan_failure_with_report_enabled_triggers_report_finalization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_scan_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            state["phase_status"]["preflight"] = "DONE"
            state["current_phase"] = "scan"
            repo = _FakeRepository(run_dir, state, {"sql_keys": []})
            record_failure = Mock()
            finalize_report = Mock()

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with self.assertRaises(StageError):
                    workflow_engine.advance_one_step(
                        run_dir,
                        {"report": {"enabled": True}, "validate": {}},
                        "patch_generate",
                        self._validator(),
                        repository=repo,
                        run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                            StageError("scan failed", reason_code="SCAN_FAILED")
                        ),
                        record_failure_fn=record_failure,
                        finalize_report_if_enabled_fn=finalize_report,
                    )

        record_failure.assert_called_once()
        self.assertEqual(record_failure.call_args.args[2], "scan")
        finalize_report.assert_called_once()
        self.assertEqual(finalize_report.call_args.kwargs["final_meta_status"], "FAILED")

    def test_advance_optimize_failure_without_report_sets_failed_meta(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_opt_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            state["phase_status"]["preflight"] = "DONE"
            state["phase_status"]["scan"] = "DONE"
            state["current_phase"] = "optimize"
            state["statements"] = {
                "demo.user.find#v1": {"optimize": "PENDING", "validate": "PENDING", "patch_generate": "PENDING"}
            }
            repo = _FakeRepository(run_dir, state, {"sql_keys": ["demo.user.find#v1"]})
            record_failure = Mock()
            finalize_report = Mock()

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with patch("sqlopt.application.workflow_engine.load_index", return_value=({"demo.user.find#v1": {}}, {}, {})):
                    with self.assertRaises(StageError):
                        workflow_engine.advance_one_step(
                            run_dir,
                            {"report": {"enabled": False}, "validate": {}},
                            "patch_generate",
                            self._validator(),
                            repository=repo,
                            run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                                StageError("optimize failed", reason_code="OPTIMIZE_FAILED")
                            ),
                            record_failure_fn=record_failure,
                            finalize_report_if_enabled_fn=finalize_report,
                        )

        record_failure.assert_called_once()
        self.assertEqual(record_failure.call_args.args[2], "optimize")
        finalize_report.assert_not_called()
        self.assertEqual(repo.meta_statuses, ["FAILED"])

    def test_advance_validate_failure_with_report_enabled_records_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_validate_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            state["phase_status"]["preflight"] = "DONE"
            state["phase_status"]["scan"] = "DONE"
            state["phase_status"]["optimize"] = "DONE"
            state["current_phase"] = "validate"
            state["statements"] = {
                "demo.user.find#v1": {"optimize": "DONE", "validate": "PENDING", "patch_generate": "PENDING"}
            }
            repo = _FakeRepository(run_dir, state, {"sql_keys": ["demo.user.find#v1"]})
            finalize_report = Mock()
            record_failure = lambda run_dir, state, phase, reason_code, message: workflow_engine.record_failure(
                run_dir, state, phase, reason_code, message, repository=repo
            )

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with patch(
                    "sqlopt.application.workflow_engine.load_index",
                    return_value=({"demo.user.find#v1": {}}, {"demo.user.find#v1": {}}, {}),
                ):
                    with self.assertRaises(StageError):
                        workflow_engine.advance_one_step(
                            run_dir,
                            {"report": {"enabled": True}, "validate": {}},
                            "patch_generate",
                            self._validator(),
                            repository=repo,
                            run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                                StageError("validate failed", reason_code="VALIDATE_FAILED")
                            ),
                            record_failure_fn=record_failure,
                            finalize_report_if_enabled_fn=finalize_report,
                        )

        self.assertEqual(state["phase_status"]["validate"], "FAILED")
        self.assertEqual(state["last_reason_code"], "VALIDATE_FAILED")
        self.assertEqual(repo.step_results[-1][0:2], ("validate", "FAILED"))
        finalize_report.assert_called_once()
        self.assertEqual(finalize_report.call_args.kwargs["final_meta_status"], "FAILED")

    def test_advance_patch_generate_failure_without_report_records_failure_and_sets_failed_meta(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_workflow_patch_fail_") as td:
            run_dir = Path(td)
            state = _initial_state()
            state["phase_status"]["preflight"] = "DONE"
            state["phase_status"]["scan"] = "DONE"
            state["phase_status"]["optimize"] = "DONE"
            state["phase_status"]["validate"] = "DONE"
            state["current_phase"] = "patch_generate"
            state["statements"] = {
                "demo.user.find#v1": {"optimize": "DONE", "validate": "DONE", "patch_generate": "PENDING"}
            }
            repo = _FakeRepository(run_dir, state, {"sql_keys": ["demo.user.find#v1"]})
            finalize_report = Mock()
            record_failure = lambda run_dir, state, phase, reason_code, message: workflow_engine.record_failure(
                run_dir, state, phase, reason_code, message, repository=repo
            )

            with patch("sqlopt.application.workflow_engine.get_progress_reporter", return_value=_DummyProgress()):
                with patch(
                    "sqlopt.application.workflow_engine.load_index",
                    return_value=({"demo.user.find#v1": {}}, {}, {"demo.user.find#v1": {"status": "PASS"}}),
                ):
                    with self.assertRaises(StageError):
                        workflow_engine.advance_one_step(
                            run_dir,
                            {"report": {"enabled": False}, "validate": {}},
                            "patch_generate",
                            self._validator(),
                            repository=repo,
                            run_phase_action_fn=lambda config, phase, fn: (_ for _ in ()).throw(
                                StageError("patch failed", reason_code="PATCH_FAILED")
                            ),
                            record_failure_fn=record_failure,
                            finalize_report_if_enabled_fn=finalize_report,
                        )

        self.assertEqual(state["phase_status"]["patch_generate"], "FAILED")
        self.assertEqual(state["last_reason_code"], "PATCH_FAILED")
        self.assertEqual(repo.step_results[-1][0:2], ("patch_generate", "FAILED"))
        finalize_report.assert_not_called()
        self.assertEqual(repo.meta_statuses, ["FAILED"])


if __name__ == "__main__":
    unittest.main()
