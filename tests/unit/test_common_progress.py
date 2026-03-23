"""Tests for ProgressTracker."""

import json

import pytest

from sqlopt.common.progress import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    VALID_STATUSES,
    ProgressTracker,
    StageProgress,
)


class TestStageProgressValidation:
    """Test StageProgress status validation."""

    def test_valid_pending_status(self):
        """Test StageProgress accepts pending status."""
        stage = StageProgress(stage_name="test", status=STATUS_PENDING)
        assert stage.status == STATUS_PENDING

    def test_valid_running_status(self):
        """Test StageProgress accepts running status."""
        stage = StageProgress(stage_name="test", status=STATUS_RUNNING)
        assert stage.status == STATUS_RUNNING

    def test_valid_completed_status(self):
        """Test StageProgress accepts completed status."""
        stage = StageProgress(stage_name="test", status=STATUS_COMPLETED)
        assert stage.status == STATUS_COMPLETED

    def test_valid_failed_status(self):
        """Test StageProgress accepts failed status."""
        stage = StageProgress(stage_name="test", status=STATUS_FAILED)
        assert stage.status == STATUS_FAILED

    def test_invalid_status_raises_error(self):
        """Test StageProgress raises ValueError for invalid status."""
        with pytest.raises(ValueError) as exc_info:
            StageProgress(stage_name="test", status="invalid_status")
        assert "Invalid status" in str(exc_info.value)

    def test_default_status_is_pending(self):
        """Test StageProgress defaults to pending status."""
        stage = StageProgress(stage_name="test")
        assert stage.status == STATUS_PENDING


class TestProgressTrackerInit:
    """Test ProgressTracker initialization."""

    def test_init_with_run_id(self):
        """Test ProgressTracker stores run_id correctly."""
        tracker = ProgressTracker(run_id="test-run-123")
        assert tracker.run_id == "test-run-123"

    def test_init_with_empty_stages(self):
        """Test ProgressTracker starts with empty stages."""
        tracker = ProgressTracker(run_id="test-run")
        assert tracker.stages == {}

    def test_init_with_callback(self):
        """Test ProgressTracker stores callback."""
        callback_called = []

        def callback(stage_name, progress):
            callback_called.append((stage_name, progress))

        tracker = ProgressTracker(run_id="test-run", callback=callback)
        assert tracker._callback is callback


class TestProgressTrackerRegisterStage:
    """Test ProgressTracker.register_stage method."""

    def test_register_new_stage(self):
        """Test registering a new stage adds it to stages."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        assert "parse" in tracker.stages
        assert tracker.stages["parse"].stage_name == "parse"
        assert tracker.stages["parse"].status == STATUS_PENDING

    def test_register_stage_does_not_duplicate(self):
        """Test registering same stage twice does not duplicate."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.register_stage("parse")
        assert len(tracker.stages) == 1


class TestProgressTrackerStartStage:
    """Test ProgressTracker.start_stage method."""

    def test_start_stage_updates_status(self):
        """Test starting a stage updates its status to running."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        assert tracker.stages["parse"].status == STATUS_RUNNING

    def test_start_stage_sets_started_at(self):
        """Test starting a stage sets started_at timestamp."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        assert tracker.stages["parse"].started_at is not None

    def test_start_stage_clears_completed_at(self):
        """Test starting a stage clears completed_at."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.complete_stage("parse")
        tracker.start_stage("parse")
        assert tracker.stages["parse"].completed_at is None

    def test_start_stage_clears_error(self):
        """Test starting a stage clears previous error."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.fail_stage("parse", "some error")
        tracker.start_stage("parse")
        assert tracker.stages["parse"].error is None

    def test_start_stage_auto_registers_if_not_exists(self):
        """Test starting a stage auto-registers it if not found."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.start_stage("new_stage")
        assert "new_stage" in tracker.stages
        assert tracker.stages["new_stage"].status == STATUS_RUNNING

    def test_start_stage_triggers_callback(self):
        """Test starting a stage triggers callback."""
        callback_calls = []

        def callback(stage_name, progress):
            callback_calls.append((stage_name, progress))

        tracker = ProgressTracker(run_id="test-run", callback=callback)
        tracker.start_stage("parse")
        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "parse"
        assert callback_calls[0][1].status == STATUS_RUNNING


class TestProgressTrackerCompleteStage:
    """Test ProgressTracker.complete_stage method."""

    def test_complete_stage_updates_status(self):
        """Test completing a stage updates status to completed."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.complete_stage("parse")
        assert tracker.stages["parse"].status == STATUS_COMPLETED

    def test_complete_stage_sets_completed_at(self):
        """Test completing a stage sets completed_at timestamp."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.complete_stage("parse")
        assert tracker.stages["parse"].completed_at is not None

    def test_complete_stage_raises_if_not_registered(self):
        """Test complete_stage raises KeyError if stage not registered."""
        tracker = ProgressTracker(run_id="test-run")
        with pytest.raises(KeyError) as exc_info:
            tracker.complete_stage("nonexistent")
        assert "not registered" in str(exc_info.value)

    def test_complete_stage_triggers_callback(self):
        """Test completing a stage triggers callback."""
        callback_calls = []

        def callback(stage_name, progress):
            callback_calls.append((stage_name, progress))

        tracker = ProgressTracker(run_id="test-run", callback=callback)
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.complete_stage("parse")
        assert len(callback_calls) == 2  # start + complete


class TestProgressTrackerFailStage:
    """Test ProgressTracker.fail_stage method."""

    def test_fail_stage_updates_status(self):
        """Test failing a stage updates status to failed."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.fail_stage("parse", "something went wrong")
        assert tracker.stages["parse"].status == STATUS_FAILED

    def test_fail_stage_sets_error_message(self):
        """Test failing a stage sets error message."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.fail_stage("parse", "connection timeout")
        assert tracker.stages["parse"].error == "connection timeout"

    def test_fail_stage_sets_completed_at(self):
        """Test failing a stage sets completed_at timestamp."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.fail_stage("parse", "error")
        assert tracker.stages["parse"].completed_at is not None

    def test_fail_stage_raises_if_not_registered(self):
        """Test fail_stage raises KeyError if stage not registered."""
        tracker = ProgressTracker(run_id="test-run")
        with pytest.raises(KeyError) as exc_info:
            tracker.fail_stage("nonexistent", "error")
        assert "not registered" in str(exc_info.value)

    def test_fail_stage_triggers_callback(self):
        """Test failing a stage triggers callback."""
        callback_calls = []

        def callback(stage_name, progress):
            callback_calls.append((stage_name, progress))

        tracker = ProgressTracker(run_id="test-run", callback=callback)
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.fail_stage("parse", "error")
        assert len(callback_calls) == 2  # start + fail


class TestProgressTrackerGetStatus:
    """Test ProgressTracker.get_status method."""

    def test_get_status_returns_run_id(self):
        """Test get_status returns run_id."""
        tracker = ProgressTracker(run_id="test-run-456")
        status = tracker.get_status()
        assert status["run_id"] == "test-run-456"

    def test_get_status_returns_stages(self):
        """Test get_status returns stages dict."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        status = tracker.get_status()
        assert "stages" in status
        assert "parse" in status["stages"]

    def test_get_status_contains_stage_progress(self):
        """Test get_status contains correct stage progress data."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("init")
        tracker.start_stage("init")
        tracker.complete_stage("init")
        status = tracker.get_status()
        init_progress = status["stages"]["init"]
        assert init_progress["stage_name"] == "init"
        assert init_progress["status"] == STATUS_COMPLETED
        assert init_progress["started_at"] is not None
        assert init_progress["completed_at"] is not None


class TestProgressTrackerJsonSerialization:
    """Test ProgressTracker JSON serialization."""

    def test_to_json_returns_valid_json(self):
        """Test to_json returns valid JSON string."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        json_str = tracker.to_json()
        # Should not raise
        parsed = json.loads(json_str)
        assert parsed["run_id"] == "test-run"

    def test_from_json_reconstructs_tracker(self):
        """Test from_json reconstructs ProgressTracker correctly."""
        tracker = ProgressTracker(run_id="original-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")
        tracker.complete_stage("parse")

        json_str = tracker.to_json()
        reconstructed = ProgressTracker.from_json(json_str)

        assert reconstructed.run_id == "original-run"
        assert "parse" in reconstructed.stages
        assert reconstructed.stages["parse"].status == STATUS_COMPLETED

    def test_roundtrip_preserves_all_fields(self):
        """Test JSON roundtrip preserves all stage fields."""
        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("optimize")
        tracker.start_stage("optimize")
        tracker.fail_stage("optimize", "test error")

        json_str = tracker.to_json()
        reconstructed = ProgressTracker.from_json(json_str)

        assert reconstructed.stages["optimize"].stage_name == "optimize"
        assert reconstructed.stages["optimize"].status == STATUS_FAILED
        assert reconstructed.stages["optimize"].error == "test error"
        assert reconstructed.stages["optimize"].started_at is not None

    def test_from_json_with_callback(self):
        """Test from_json accepts callback parameter."""
        callback_calls = []

        def callback(stage_name, progress):
            callback_calls.append((stage_name, progress))

        tracker = ProgressTracker(run_id="test-run")
        tracker.register_stage("parse")
        tracker.start_stage("parse")

        json_str = tracker.to_json()
        reconstructed = ProgressTracker.from_json(json_str, callback=callback)

        # Callback should be triggered on future operations
        reconstructed.start_stage("parse")
        assert len(callback_calls) >= 1


class TestValidStatuses:
    """Test status constants."""

    def test_valid_statuses_contains_expected_values(self):
        """Test VALID_STATUSES contains all expected status values."""
        assert STATUS_PENDING in VALID_STATUSES
        assert STATUS_RUNNING in VALID_STATUSES
        assert STATUS_COMPLETED in VALID_STATUSES
        assert STATUS_FAILED in VALID_STATUSES
        assert len(VALID_STATUSES) == 4
