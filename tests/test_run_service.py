from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.application import run_service
from sqlopt.application.requests import AdvanceStepRequest, RunStatusRequest


class _RepoStub:
    init_calls = 0
    write_cfg_calls = 0
    meta_statuses: list[str] = []
    plans_set: list[dict] = []
    state: dict = {}
    plan: dict = {}
    meta: dict = {}

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    @classmethod
    def reset(cls) -> None:
        cls.init_calls = 0
        cls.write_cfg_calls = 0
        cls.meta_statuses = []
        cls.plans_set = []
        cls.state = {}
        cls.plan = {"to_stage": "patch_generate"}
        cls.meta = {"status": "RUNNING"}

    def initialize(self, config: dict, run_id: str) -> None:
        type(self).init_calls += 1
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_resolved_config(self, config: dict) -> None:
        type(self).write_cfg_calls += 1

    def set_meta_status(self, status: str) -> None:
        type(self).meta_statuses.append(status)

    def get_plan(self) -> dict:
        return dict(type(self).plan)

    def set_plan(self, plan: dict) -> None:
        type(self).plan = dict(plan)
        type(self).plans_set.append(dict(plan))

    def load_state(self) -> dict:
        return dict(type(self).state)

    def load_meta(self) -> dict:
        return dict(type(self).meta)


class RunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        _RepoStub.reset()

    def test_start_run_initializes_only_once_for_existing_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_service_") as td:
            project_root = Path(td) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            config_path = project_root / "sqlopt.yml"
            config_path.write_text("{}", encoding="utf-8")
            config = {"project": {"root_path": str(project_root)}}

            with patch("sqlopt.application.run_service.load_config", return_value=config):
                with patch("sqlopt.application.run_service.RunRepository", _RepoStub):
                    with patch("sqlopt.application.run_service.run_index.remember_run"):
                        with patch(
                            "sqlopt.application.run_service.workflow_engine.advance_one_step_request",
                            return_value={"complete": False, "phase": "preflight"},
                        ):
                            run_id_1, _ = run_service.start_run(config_path, "patch_generate", "run_fixed", repo_root=project_root)
                            run_id_2, _ = run_service.start_run(config_path, "patch_generate", "run_fixed", repo_root=project_root)

        self.assertEqual(run_id_1, "run_fixed")
        self.assertEqual(run_id_2, "run_fixed")
        self.assertEqual(_RepoStub.init_calls, 1)
        self.assertEqual(_RepoStub.write_cfg_calls, 1)
        self.assertEqual(_RepoStub.meta_statuses, ["RUNNING", "RUNNING"])
        self.assertEqual(_RepoStub.plans_set[-1]["to_stage"], "patch_generate")

    def test_resume_run_builds_advance_request_from_saved_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_resume_service_") as td:
            run_dir = Path(td) / "runs" / "run_resume"
            run_dir.mkdir(parents=True, exist_ok=True)
            _RepoStub.plan = {"to_stage": "validate"}

            with patch("sqlopt.application.run_service.run_index.resolve_run_dir", return_value=run_dir):
                with patch("sqlopt.application.run_service.load_config", return_value={"project": {"root_path": str(run_dir.parent)}}):
                    with patch("sqlopt.application.run_service.RunRepository", _RepoStub):
                        with patch("sqlopt.application.run_service.workflow_engine.advance_one_step_request") as advance:
                            advance.return_value = {"complete": False, "phase": "validate"}
                            result = run_service.resume_run("run_resume", repo_root=run_dir.parent)

        self.assertEqual(result["phase"], "validate")
        request = advance.call_args.args[0]
        self.assertIsInstance(request, AdvanceStepRequest)
        self.assertEqual(request.run_dir, run_dir)
        self.assertEqual(request.to_stage, "validate")

    def test_resume_run_defaults_to_patch_generate_without_saved_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_resume_default_") as td:
            run_dir = Path(td) / "runs" / "run_resume_default"
            run_dir.mkdir(parents=True, exist_ok=True)
            _RepoStub.plan = {}

            with patch("sqlopt.application.run_service.run_index.resolve_run_dir", return_value=run_dir):
                with patch("sqlopt.application.run_service.load_config", return_value={"project": {"root_path": str(run_dir.parent)}}):
                    with patch("sqlopt.application.run_service.RunRepository", _RepoStub):
                        with patch("sqlopt.application.run_service.workflow_engine.advance_one_step_request") as advance:
                            advance.return_value = {"complete": False, "phase": "patch_generate"}
                            result = run_service.resume_run("run_resume_default", repo_root=run_dir.parent)

        self.assertEqual(result["phase"], "patch_generate")
        request = advance.call_args.args[0]
        self.assertIsInstance(request, AdvanceStepRequest)
        self.assertEqual(request.to_stage, "patch_generate")

    def test_get_status_uses_snapshot_builder_without_stage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_status_service_") as td:
            run_dir = Path(td) / "runs" / "run_status"
            run_dir.mkdir(parents=True, exist_ok=True)
            _RepoStub.state = {
                "current_phase": "scan",
                "phase_status": {"preflight": "DONE", "scan": "PENDING"},
                "statements": {},
                "attempts_by_phase": {},
                "last_reason_code": None,
            }
            _RepoStub.plan = {"to_stage": "patch_generate"}
            _RepoStub.meta = {"status": "RUNNING"}
            expected = {"run_id": "run_status", "complete": False}

            with patch("sqlopt.application.run_service.run_index.resolve_run_dir", return_value=run_dir):
                with patch("sqlopt.application.run_service.load_config", return_value={"report": {"enabled": True}}):
                    with patch("sqlopt.application.run_service.RunRepository", _RepoStub):
                        with patch("sqlopt.application.run_service.workflow_engine.build_status_snapshot", return_value=expected) as snapshot:
                            result = run_service.get_status("run_status", repo_root=run_dir.parent)

        self.assertEqual(result, expected)
        request = snapshot.call_args.args[0]
        self.assertIsInstance(request, RunStatusRequest)
        self.assertEqual(request.run_id, "run_status")
        self.assertEqual(request.state["current_phase"], "scan")

    def test_apply_run_uses_resolved_run_dir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_apply_service_") as td:
            run_dir = Path(td) / "runs" / "run_apply"
            run_dir.mkdir(parents=True, exist_ok=True)
            with patch("sqlopt.application.run_service.run_index.resolve_run_dir", return_value=run_dir):
                with patch("sqlopt.application.run_service.apply_stage.apply_from_config", return_value={"applied": False}) as apply_mock:
                    result = run_service.apply_run("run_apply", repo_root=run_dir.parent)

        self.assertEqual(result, {"run_id": "run_apply", "apply": {"applied": False}})
        apply_mock.assert_called_once_with(run_dir)


if __name__ == "__main__":
    unittest.main()
