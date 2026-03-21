#!/usr/bin/env python3
"""
V9 Workflow Engine Integration Tests

Tests the complete V9 workflow execution flow including:
1. Normal execution (run method)
2. Single step execution (advance_one_step method)
3. Resume execution (resume method)
4. Exception handling and state updates
5. Stage execution with mocked dependencies

This test captures current behavior as regression test baseline.
Do NOT modify existing behavior - only test what exists.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch, MagicMock, call
from uuid import uuid4

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_config():
    """Minimal config for testing."""
    return {
        "config_version": "v1",
        "project": {"root_path": "."},
        "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
        "db": {
            "platform": "postgresql",
            "dsn": "postgresql://user:pass@localhost:5432/testdb",
        },
        "llm": {"enabled": False},
    }


@pytest.fixture
def mock_repository():
    """Mock repository for state persistence."""
    repo = Mock()
    repo.save_state = Mock()
    repo.load_state = Mock(
        return_value={
            "run_id": "",
            "current_stage": "",
            "completed_stages": [],
            "stage_results": {},
            "started_at": "",
            "updated_at": "",
            "status": "pending",
        }
    )
    repo.initialize = Mock()
    return repo


@pytest.fixture
def temp_run_dir(tmp_path):
    """Create a temporary run directory."""
    run_dir = tmp_path / "runs" / f"test_run_{uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@pytest.fixture
def workflow_engine(mock_config, mock_repository):
    """Create a V9WorkflowEngine with mocked dependencies."""
    with patch("sqlopt.application.workflow_v9.StatusResolver") as mock_resolver:
        mock_resolver_instance = Mock()
        mock_resolver_instance.is_complete_to_stage = Mock(return_value=False)
        mock_resolver.return_value = mock_resolver_instance

        from sqlopt.application.workflow_v9 import V9WorkflowEngine

        engine = V9WorkflowEngine(
            config=mock_config,
            repository=mock_repository,
            run_id="test_run_001",
        )
        return engine


# =============================================================================
# V9WorkflowEngine Initialization Tests
# =============================================================================


class TestWorkflowEngineInitialization:
    """Tests for V9WorkflowEngine initialization."""

    def test_engine_initializes_with_config(self, mock_config, mock_repository):
        """Test engine initializes with provided config."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config,
                repository=mock_repository,
                run_id="test_init_001",
            )

            assert engine.config == mock_config
            assert engine.repository == mock_repository
            assert engine.run_id == "test_init_001"

    def test_engine_generates_run_id_if_not_provided(self, mock_config):
        """Test engine generates run_id when not provided."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config)

            assert engine.run_id.startswith("run_")
            assert len(engine.run_id) > 10

    def test_engine_initializes_with_default_state(self, mock_config):
        """Test engine initializes with default state."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config)

            assert engine.state.run_id == engine.run_id
            assert engine.state.status == "pending"
            assert engine.state.current_stage == ""
            assert engine.state.completed_stages == []
            assert engine.state.stage_results == {}
            assert engine.state.started_at != ""

    def test_engine_registers_all_stages(self, mock_config):
        """Test engine registers all 7 stages."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config)

            expected_stages = [
                "init",
                "parse",
                "recognition",
                "optimize",
                "patch",
            ]
            for stage in expected_stages:
                assert stage in engine.stages
                assert callable(engine.stages[stage])


# =============================================================================
# V9WorkflowEngine.run() Tests
# =============================================================================


class TestWorkflowEngineRun:
    """Tests for V9WorkflowEngine.run() method."""

    def test_run_sets_status_after_run(self, mock_config, temp_run_dir):
        """Test that run() completes successfully with repository=None."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            engine.stages = {
                "init": lambda r: {"success": True},
                "parse": lambda r: {"success": True},
                "recognition": lambda r: {"success": True},
                "optimize": lambda r: {"success": True},
                "patch": lambda r: {"success": True},
            }

            # Run to init stage
            engine.run(temp_run_dir, to_stage="init")

            # Init completes successfully - stages are tracked
            assert "init" in engine.state.completed_stages

    def test_run_executes_stages_in_order(self, workflow_engine, temp_run_dir):
        """Test that run() executes stages in correct order."""
        call_order = []

        def mock_stage(run_dir):
            call_order.append("stage")
            return {"success": True}

        workflow_engine.stages = {
            "init": lambda r: (call_order.append("init"), {"success": True})[1],
            "parse": lambda r: (call_order.append("parse"), {"success": True})[1],
            "recognition": lambda r: (
                call_order.append("recognition"),
                {"success": True},
            )[1],
            "optimize": lambda r: (call_order.append("optimize"), {"success": True})[1],
            "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
        }

        workflow_engine.run(temp_run_dir, to_stage="patch")

        assert call_order == [
            "init",
            "parse",
            "recognition",
            "optimize",
            "patch",
        ]

    def test_run_stops_on_first_failure(self, workflow_engine, temp_run_dir):
        """Test that run() stops execution when a stage fails."""
        call_order = []

        workflow_engine.stages = {
            "init": lambda r: (call_order.append("init"), {"success": True})[1],
            "parse": lambda r: (
                call_order.append("parse"),
                {"success": False, "error": "Test error"},
            )[1],
            "recognition": lambda r: (
                call_order.append("recognition"),
                {"success": True},
            )[1],
            "optimize": lambda r: (call_order.append("optimize"), {"success": True})[1],
            "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
        }

        results = workflow_engine.run(temp_run_dir, to_stage="patch")

        assert "init" in call_order
        assert "parse" in call_order
        assert "recognition" not in call_order  # Should not execute
        assert results["parse"]["success"] is False
        assert workflow_engine.state.status == "failed"

    def test_run_respects_to_stage_limit(self, workflow_engine, temp_run_dir):
        """Test that run() stops at to_stage."""
        call_order = []

        workflow_engine.stages = {
            "init": lambda r: (call_order.append("init"), {"success": True})[1],
            "parse": lambda r: (call_order.append("parse"), {"success": True})[1],
            "recognition": lambda r: (
                call_order.append("recognition"),
                {"success": True},
            )[1],
            "optimize": lambda r: (call_order.append("optimize"), {"success": True})[1],
            "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
        }

        workflow_engine.run(temp_run_dir, to_stage="recognition")

        assert call_order == [
            "init",
            "parse",
            "recognition",
        ]
        assert "optimize" not in call_order
        assert "patch" not in call_order

    def test_run_updates_completed_stages(self, workflow_engine, temp_run_dir):
        """Test that run() updates completed_stages after each stage."""
        workflow_engine.stages = {
            "init": lambda r: {"success": True},
            "parse": lambda r: {"success": True},
            "recognition": lambda r: {"success": True},
            "optimize": lambda r: {"success": True},
            "patch": lambda r: {"success": True},
        }

        workflow_engine.run(temp_run_dir, to_stage="patch")

        assert "init" in workflow_engine.state.completed_stages
        assert "parse" in workflow_engine.state.completed_stages
        assert "recognition" in workflow_engine.state.completed_stages
        assert "optimize" in workflow_engine.state.completed_stages
        assert "patch" in workflow_engine.state.completed_stages

    def test_run_handles_stage_exception(self, workflow_engine, temp_run_dir):
        """Test that run() handles exceptions from stages."""
        workflow_engine.stages = {
            "init": lambda r: (_ for _ in ()).throw(Exception("Stage error")),
            "parse": lambda r: {"success": True},
            "recognition": lambda r: {"success": True},
            "optimize": lambda r: {"success": True},
            "patch": lambda r: {"success": True},
        }

        results = workflow_engine.run(temp_run_dir, to_stage="patch")

        assert results["init"]["success"] is False
        assert "Stage error" in results["init"]["error"]
        assert workflow_engine.state.status == "failed"

    def test_run_sets_completed_when_all_stages_done(
        self, workflow_engine, temp_run_dir
    ):
        """Test that run() sets status to 'completed' when all stages finish."""
        workflow_engine.stages = {
            "init": lambda r: {"success": True},
            "parse": lambda r: {"success": True},
            "recognition": lambda r: {"success": True},
            "optimize": lambda r: {"success": True},
            "patch": lambda r: {"success": True},
        }

        workflow_engine.run(temp_run_dir, to_stage="patch")

        assert workflow_engine.state.status == "completed"


# =============================================================================
# V9WorkflowEngine.advance_one_step() Tests
# =============================================================================


class TestAdvanceOneStep:
    """Tests for V9WorkflowEngine.advance_one_step() method."""

    def test_advance_one_step_returns_completed_when_all_done(
        self, mock_config, temp_run_dir
    ):
        """Test advance_one_step returns completed=True when all stages done."""
        # Create a mock repo that returns state with all stages completed
        mock_repo = Mock()
        mock_repo.load_state = Mock(
            return_value={
                "run_id": "test_run",
                "current_stage": "patch",
                "completed_stages": [
                    "init",
                    "parse",
                    "recognition",
                    "optimize",
                    "patch",
                ],
                "stage_results": {},
                "started_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:01:00Z",
                "status": "completed",
            }
        )
        mock_repo.save_state = Mock()
        mock_repo.initialize = Mock()

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config, repository=mock_repo, run_id="test_run"
            )

            result = engine.advance_one_step(temp_run_dir, to_stage="patch")

            assert result["completed"] is True
            assert result["stage"] is None

    def test_advance_one_step_executes_next_stage(self, mock_config, temp_run_dir):
        """Test advance_one_step executes the next uncompleted stage."""
        call_order = []

        # Use repository that returns empty state (fresh start)
        mock_repo = Mock()
        mock_repo.load_state = Mock(return_value={})
        mock_repo.save_state = Mock()
        mock_repo.initialize = Mock()

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config, repository=mock_repo, run_id="test_run"
            )
            engine.stages = {
                "init": lambda r: (
                    call_order.append("init"),
                    {"success": True},
                )[1],
                "parse": lambda r: (
                    call_order.append("parse"),
                    {"success": True},
                )[1],
                "recognition": lambda r: (
                    call_order.append("recognition"),
                    {"success": True},
                )[1],
                "optimize": lambda r: (
                    call_order.append("optimize"),
                    {"success": True},
                )[1],
                "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
            }

            # First call should do init
            result1 = engine.advance_one_step(temp_run_dir, to_stage="patch")
            assert result1["completed"] is False
            assert result1["stage"] == "init"
            assert "init" in call_order

            # Second call should do parse
            result2 = engine.advance_one_step(temp_run_dir, to_stage="patch")
            assert result2["completed"] is False
            assert result2["stage"] == "parse"
            assert "parse" in call_order

    def test_advance_one_step_handles_stage_failure(self, mock_config, temp_run_dir):
        """Test advance_one_step handles stage failure."""
        mock_repo = Mock()
        mock_repo.load_state = Mock(return_value={})
        mock_repo.save_state = Mock()
        mock_repo.initialize = Mock()

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config, repository=mock_repo, run_id="test_run"
            )
            engine.stages = {
                "init": lambda r: {"success": False, "error": "Init failed"},
                "parse": lambda r: {"success": True},
                "recognition": lambda r: {"success": True},
                "optimize": lambda r: {"success": True},
                "patch": lambda r: {"success": True},
            }

            result = engine.advance_one_step(temp_run_dir, to_stage="patch")

            assert result["completed"] is False
            assert result["stage"] == "init"
            assert result["result"]["success"] is False
            assert engine.state.status == "failed"

    def test_advance_one_step_handles_exception(self, mock_config, temp_run_dir):
        """Test advance_one_step handles exceptions."""
        mock_repo = Mock()
        mock_repo.load_state = Mock(return_value={})
        mock_repo.save_state = Mock()
        mock_repo.initialize = Mock()

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config, repository=mock_repo, run_id="test_run"
            )
            engine.stages = {
                "init": lambda r: (_ for _ in ()).throw(Exception("Test exception")),
                "parse": lambda r: {"success": True},
                "recognition": lambda r: {"success": True},
                "optimize": lambda r: {"success": True},
                "patch": lambda r: {"success": True},
            }

            result = engine.advance_one_step(temp_run_dir, to_stage="patch")

            assert result["completed"] is False
            assert result["result"]["success"] is False
            assert "Test exception" in result["result"]["error"]

    def test_advance_one_step_returns_state_snapshot(self, mock_config, temp_run_dir):
        """Test advance_one_step returns state snapshot in result."""
        mock_repo = Mock()
        mock_repo.load_state = Mock(return_value={})
        mock_repo.save_state = Mock()
        mock_repo.initialize = Mock()

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(
                config=mock_config, repository=mock_repo, run_id="test_run"
            )
            engine.stages = {
                "init": lambda r: {"success": True},
                "parse": lambda r: {"success": True},
                "recognition": lambda r: {"success": True},
                "optimize": lambda r: {"success": True},
                "patch": lambda r: {"success": True},
            }

            result = engine.advance_one_step(temp_run_dir, to_stage="patch")

            assert "state" in result
            assert "run_id" in result["state"]
            assert "current_stage" in result["state"]
            assert "completed_stages" in result["state"]
            assert "status" in result["state"]


# =============================================================================
# V9WorkflowEngine.resume() Tests
# =============================================================================


class TestResume:
    """Tests for V9WorkflowEngine.resume() method."""

    def test_resume_loads_existing_state_and_continues(self, mock_config, temp_run_dir):
        """Test resume() loads existing state from run_dir and continues execution."""
        # Create state file with init completed
        supervisor_dir = temp_run_dir / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)

        saved_state = {
            "run_id": "resumed_run",
            "current_stage": "parse",
            "completed_stages": ["init"],
            "stage_results": {
                "init": {"success": True, "output_file": "/path/to/output.json"}
            },
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }

        state_file = supervisor_dir / "state.json"
        state_file.write_text(json.dumps(saved_state))

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            engine.stages = {
                "init": lambda r: {"success": True},
                "parse": lambda r: {"success": True},
                "recognition": lambda r: {"success": True},
                "optimize": lambda r: {"success": True},
                "patch": lambda r: {"success": True},
            }

            results = engine.resume(temp_run_dir, to_stage="patch")

            # Verify that resume loaded the state
            assert engine.state.run_id == "resumed_run"
            # init should still be completed, and all other stages should now be completed too
            assert "init" in engine.state.completed_stages
            # All stages should have run since state only had init completed
            assert len(engine.state.completed_stages) == 5

    def test_resume_skips_completed_stages(self, mock_config, temp_run_dir):
        """Test resume() skips already completed stages."""
        call_order = []

        # Create state file with init and parse completed
        supervisor_dir = temp_run_dir / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)

        saved_state = {
            "run_id": "resumed_run",
            "current_stage": "recognition",
            "completed_stages": ["init", "parse"],
            "stage_results": {
                "init": {"success": True},
                "parse": {"success": True},
            },
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }

        state_file = supervisor_dir / "state.json"
        state_file.write_text(json.dumps(saved_state))

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            engine.stages = {
                "init": lambda r: (
                    call_order.append("init"),
                    {"success": True},
                )[1],
                "parse": lambda r: (
                    call_order.append("parse"),
                    {"success": True},
                )[1],
                "recognition": lambda r: (
                    call_order.append("recognition"),
                    {"success": True},
                )[1],
                "optimize": lambda r: (
                    call_order.append("optimize"),
                    {"success": True},
                )[1],
                "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
            }

            engine.resume(temp_run_dir, to_stage="patch")

            # Init and parse should NOT be called (already completed)
            assert "init" not in call_order
            assert "parse" not in call_order
            # But recognition and subsequent stages should run
            assert "recognition" in call_order
            assert "optimize" in call_order

    def test_resume_stops_on_failure(self, mock_config, temp_run_dir):
        """Test resume() stops when a stage fails."""
        call_order = []

        # Create state file with init completed
        supervisor_dir = temp_run_dir / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)

        saved_state = {
            "run_id": "resumed_run",
            "current_stage": "parse",
            "completed_stages": ["init"],
            "stage_results": {"init": {"success": True}},
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }

        state_file = supervisor_dir / "state.json"
        state_file.write_text(json.dumps(saved_state))

        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            engine.stages = {
                "init": lambda r: (
                    call_order.append("init"),
                    {"success": True},
                )[1],
                "parse": lambda r: (
                    call_order.append("parse"),
                    {"success": False, "error": "Failed"},
                )[1],
                "recognition": lambda r: (
                    call_order.append("recognition"),
                    {"success": True},
                )[1],
                "optimize": lambda r: (
                    call_order.append("optimize"),
                    {"success": True},
                )[1],
                "patch": lambda r: (call_order.append("patch"), {"success": True})[1],
            }

            results = engine.resume(temp_run_dir, to_stage="patch")

            # init is already done, parse should run and fail
            assert "parse" in call_order
            # recognition should NOT run (stopped after failure)
            assert "recognition" not in call_order
            assert results["parse"]["success"] is False

    def test_resume_saves_state_after_completion(self, workflow_engine, temp_run_dir):
        """Test resume() saves state after completing stages."""
        workflow_engine.stages = {
            "init": lambda r: {"success": True},
            "parse": lambda r: {"success": True},
            "recognition": lambda r: {"success": True},
            "optimize": lambda r: {"success": True},
            "patch": lambda r: {"success": True},
        }

        workflow_engine.resume(temp_run_dir, to_stage="patch")

        # Verify state file was created
        state_file = temp_run_dir / "supervisor" / "state.json"
        assert state_file.exists()

        saved_state = json.loads(state_file.read_text())
        assert saved_state["run_id"] == workflow_engine.run_id
        assert "patch" in saved_state["completed_stages"]


# =============================================================================
# V9WorkflowEngine.get_next_action() Tests
# =============================================================================


class TestGetNextAction:
    """Tests for V9WorkflowEngine.get_next_action() method."""

    def test_get_next_action_returns_run_when_no_state(
        self, workflow_engine, temp_run_dir
    ):
        """Test get_next_action returns 'run' action when no previous state."""
        action = workflow_engine.get_next_action(temp_run_dir)

        assert action.action == "run"
        assert action.stage == "init"
        assert "No previous state" in action.reason

    def test_get_next_action_returns_none_when_complete(
        self, workflow_engine, temp_run_dir
    ):
        """Test get_next_action returns 'none' when already complete."""
        # Create state file with all stages completed
        supervisor_dir = temp_run_dir / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)

        saved_state = {
            "run_id": "test_run",
            "current_stage": "patch",
            "completed_stages": [
                "init",
                "parse",
                "recognition",
                "optimize",
                "patch",
            ],
            "stage_results": {},
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "completed",
        }

        state_file = supervisor_dir / "state.json"
        state_file.write_text(json.dumps(saved_state))

        action = workflow_engine.get_next_action(temp_run_dir)

        assert action.action == "none"
        assert action.stage is None

    def test_get_next_action_returns_resume_when_partial(
        self, workflow_engine, temp_run_dir
    ):
        """Test get_next_action returns 'resume' when partially complete."""
        supervisor_dir = temp_run_dir / "supervisor"
        supervisor_dir.mkdir(parents=True, exist_ok=True)

        saved_state = {
            "run_id": "test_run",
            "current_stage": "parse",
            "completed_stages": ["init"],
            "stage_results": {"init": {"success": True}},
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }

        state_file = supervisor_dir / "state.json"
        state_file.write_text(json.dumps(saved_state))

        action = workflow_engine.get_next_action(temp_run_dir)

        assert action.action == "resume"
        assert action.stage == "parse"


# =============================================================================
# V9WorkflowEngine Stage Methods Tests
# =============================================================================


class TestStageMethods:
    """Tests for individual stage execution methods."""

    def test_run_init_creates_output_file(self, mock_config, temp_run_dir):
        """Test _run_init creates output file with sql_units."""
        # Mock Scanner at the source
        mock_result = Mock()
        mock_result.sql_units = [
            {"sqlKey": "test1", "sql": "SELECT * FROM users"},
            {"sqlKey": "test2", "sql": "SELECT * FROM orders"},
        ]
        mock_result.total_count = 2
        mock_result.errors = []
        mock_result.warnings = []

        with patch("sqlopt.application.v9_stages.init.Scanner") as mock_scanner_class:
            mock_scanner_instance = Mock()
            mock_scanner_instance.scan.return_value = mock_result
            mock_scanner_class.return_value = mock_scanner_instance

            with patch("sqlopt.application.workflow_v9.StatusResolver"):
                from sqlopt.application.workflow_v9 import V9WorkflowEngine

                engine = V9WorkflowEngine(config=mock_config, repository=None)
                result = engine._run_init(temp_run_dir)

                assert result["success"] is True
                assert result["sql_units_count"] == 2

                output_path = temp_run_dir / "init" / "sql_units.json"
                assert output_path.exists()

                saved_data = json.loads(output_path.read_text())
                assert len(saved_data) == 2

    def test_run_parse_returns_error_when_no_init(self, mock_config, temp_run_dir):
        """Test _run_parse returns error when init output missing."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            result = engine._run_parse(temp_run_dir)

            assert result["success"] is False
            assert "not found" in result["error"]


class TestStageMethodsContinuation:
    """Continuation of stage method tests - tests actual stage behavior."""

    def test_run_recognition_returns_error_when_no_parse(
        self, mock_config, temp_run_dir
    ):
        """Test _run_recognition returns error when parse output missing."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            result = engine._run_recognition(temp_run_dir)

            assert result["success"] is False
            assert "not found" in result["error"]

    def test_run_optimize_returns_error_when_no_recognition(
        self, mock_config, temp_run_dir
    ):
        """Test _run_optimize returns error when recognition output missing."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            result = engine._run_optimize(temp_run_dir)

            assert result["success"] is False
            assert "not found" in result["error"]

    def test_run_patch_returns_error_when_no_optimize(self, mock_config, temp_run_dir):
        """Test _run_patch returns error when optimize output missing."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            result = engine._run_patch(temp_run_dir)

            assert result["success"] is False
            assert "not found" in result["error"]


# =============================================================================
# State Persistence Tests
# =============================================================================


class TestStatePersistence:
    """Tests for state persistence functionality."""

    def test_persist_state_calls_repository_save(
        self, workflow_engine, mock_repository
    ):
        """Test _persist_state calls repository.save_state."""
        workflow_engine._persist_state()

        mock_repository.save_state.assert_called_once()
        call_args = mock_repository.save_state.call_args[0][0]

        assert call_args["run_id"] == workflow_engine.run_id
        assert call_args["status"] == "pending"
        assert "completed_stages" in call_args

    def test_load_state_from_repo_loads_v9_format(
        self, workflow_engine, mock_repository
    ):
        """Test load_state_from_repo handles V9 format."""
        saved_state = {
            "run_id": "loaded_run",
            "current_stage": "optimize",
            "completed_stages": ["init", "parse"],
            "stage_results": {"init": {"success": True}},
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }
        mock_repository.load_state = Mock(return_value=saved_state)

        workflow_engine.load_state_from_repo()

        assert workflow_engine.state.run_id == "loaded_run"
        assert workflow_engine.state.current_stage == "optimize"
        assert "init" in workflow_engine.state.completed_stages
        assert "parse" in workflow_engine.state.completed_stages

    def test_save_and_load_state_roundtrip(self, mock_config, temp_run_dir):
        """Test state save and load produces consistent results."""
        with patch("sqlopt.application.workflow_v9.StatusResolver"):
            from sqlopt.application.workflow_v9 import V9WorkflowEngine

            engine = V9WorkflowEngine(config=mock_config, repository=None)
            engine.state.completed_stages = ["init", "parse"]
            engine.state.current_stage = "recognition"
            engine.state.status = "running"

            # Save state
            engine._save_state(temp_run_dir)

            # Load into new state object
            from sqlopt.application.workflow_v9 import V9WorkflowState

            state_file = temp_run_dir / "supervisor" / "state.json"
            loaded_data = json.loads(state_file.read_text())

            new_state = V9WorkflowState(**loaded_data)

            assert new_state.completed_stages == ["init", "parse"]
            assert new_state.current_stage == "recognition"
            assert new_state.status == "running"


# =============================================================================
# Helper Functions Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_run_v9_workflow_creates_engine_and_runs(self, mock_config, temp_run_dir):
        """Test run_v9_workflow creates engine and calls run."""
        with patch(
            "sqlopt.application.workflow_v9.V9WorkflowEngine"
        ) as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = {"init": {"success": True}}
            mock_engine_class.return_value = mock_engine

            from sqlopt.application.workflow_v9 import run_v9_workflow

            result = run_v9_workflow(mock_config, temp_run_dir, to_stage="init")

            mock_engine_class.assert_called_once_with(mock_config)
            mock_engine.run.assert_called_once_with(temp_run_dir, "init")
            assert result == {"init": {"success": True}}

    def test_runs_root_returns_correct_path(self, mock_config):
        """Test runs_root returns correct path based on config."""
        mock_config["project"]["root_path"] = "/project/root"

        from sqlopt.application.workflow_v9 import runs_root

        result = runs_root(mock_config)

        assert result == Path("/project/root/runs")

    def test_persist_state_calls_repository_save(
        self, workflow_engine, mock_repository
    ):
        """Test _persist_state calls repository.save_state."""
        workflow_engine._persist_state()

        mock_repository.save_state.assert_called_once()
        call_args = mock_repository.save_state.call_args[0][0]

        assert call_args["run_id"] == workflow_engine.run_id
        assert call_args["status"] == "pending"
        assert "completed_stages" in call_args

    def test_load_state_from_repo_loads_v9_format(
        self, workflow_engine, mock_repository
    ):
        """Test load_state_from_repo handles V9 format."""
        saved_state = {
            "run_id": "loaded_run",
            "current_stage": "optimize",
            "completed_stages": ["init", "parse"],
            "stage_results": {"init": {"success": True}},
            "started_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:01:00Z",
            "status": "running",
        }
        mock_repository.load_state.return_value = saved_state

        workflow_engine.load_state_from_repo()

        assert workflow_engine.state.run_id == "loaded_run"
        assert workflow_engine.state.current_stage == "optimize"
        assert "init" in workflow_engine.state.completed_stages
        assert "parse" in workflow_engine.state.completed_stages

    def test_save_and_load_state_roundtrip(self, workflow_engine, temp_run_dir):
        """Test state save and load produces consistent results."""
        workflow_engine.state.completed_stages = ["init", "parse"]
        workflow_engine.state.current_stage = "recognition"
        workflow_engine.state.status = "running"

        # Save state
        workflow_engine._save_state(temp_run_dir)

        # Load into new state object
        from sqlopt.application.workflow_v9 import V9WorkflowState

        state_file = temp_run_dir / "supervisor" / "state.json"
        loaded_data = json.loads(state_file.read_text())

        new_state = V9WorkflowState(**loaded_data)

        assert new_state.completed_stages == ["init", "parse"]
        assert new_state.current_stage == "recognition"
        assert new_state.status == "running"


# =============================================================================
# Helper Functions Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_run_v9_workflow_creates_engine_and_runs(self, mock_config, temp_run_dir):
        """Test run_v9_workflow creates engine and calls run."""
        with patch(
            "sqlopt.application.workflow_v9.V9WorkflowEngine"
        ) as mock_engine_class:
            mock_engine = Mock()
            mock_engine.run.return_value = {"init": {"success": True}}
            mock_engine_class.return_value = mock_engine

            from sqlopt.application.workflow_v9 import run_v9_workflow

            result = run_v9_workflow(mock_config, temp_run_dir, to_stage="init")

            mock_engine_class.assert_called_once_with(mock_config)
            mock_engine.run.assert_called_once_with(temp_run_dir, "init")
            assert result == {"init": {"success": True}}

    def test_runs_root_returns_correct_path(self, mock_config):
        """Test runs_root returns correct path based on config."""
        mock_config["project"]["root_path"] = "/project/root"

        from sqlopt.application.workflow_v9 import runs_root

        result = runs_root(mock_config)

        assert result == Path("/project/root/runs")


# =============================================================================
# STAGE_ORDER Constant Tests
# =============================================================================


class TestStageOrder:
    """Tests for STAGE_ORDER constant."""

    def test_stage_order_has_five_stages(self):
        """Test STAGE_ORDER contains all 5 V9 stages."""
        from sqlopt.application.workflow_v9 import STAGE_ORDER

        expected = [
            "init",
            "parse",
            "recognition",
            "optimize",
            "patch",
        ]
        assert STAGE_ORDER == expected

    def test_stage_order_is_correct_sequence(self):
        """Test STAGE_ORDER is in correct execution sequence."""
        from sqlopt.application.workflow_v9 import STAGE_ORDER

        assert STAGE_ORDER.index("init") < STAGE_ORDER.index("parse")
        assert STAGE_ORDER.index("parse") < STAGE_ORDER.index("recognition")
        assert STAGE_ORDER.index("recognition") < STAGE_ORDER.index("optimize")
        assert STAGE_ORDER.index("optimize") < STAGE_ORDER.index("patch")


# =============================================================================
# V9WorkflowState Dataclass Tests
# =============================================================================


class TestV9WorkflowState:
    """Tests for V9WorkflowState dataclass."""

    def test_v9_workflow_state_default_values(self):
        """Test V9WorkflowState default values."""
        from sqlopt.application.workflow_v9 import V9WorkflowState

        state = V9WorkflowState()

        assert state.run_id == ""
        assert state.current_stage == ""
        assert state.completed_stages == []
        assert state.stage_results == {}
        assert state.started_at == ""
        assert state.updated_at == ""
        assert state.status == "pending"

    def test_v9_workflow_state_with_values(self):
        """Test V9WorkflowState with provided values."""
        from sqlopt.application.workflow_v9 import V9WorkflowState

        state = V9WorkflowState(
            run_id="test_run",
            current_stage="init",
            completed_stages=["init", "parse"],
            stage_results={"init": {"success": True}},
            started_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:01:00Z",
            status="running",
        )

        assert state.run_id == "test_run"
        assert state.current_stage == "init"
        assert len(state.completed_stages) == 2
        assert state.status == "running"


# =============================================================================
# NextAction Dataclass Tests
# =============================================================================


class TestNextAction:
    """Tests for NextAction dataclass."""

    def test_next_action_default_values(self):
        """Test NextAction default values."""
        from sqlopt.application.workflow_v9 import NextAction

        action = NextAction(action="run")

        assert action.action == "run"
        assert action.stage is None
        assert action.reason == ""

    def test_next_action_with_values(self):
        """Test NextAction with provided values."""
        from sqlopt.application.workflow_v9 import NextAction

        action = NextAction(action="resume", stage="init", reason="Start fresh run")

        assert action.action == "resume"
        assert action.stage == "init"
        assert action.reason == "Start fresh run"


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
