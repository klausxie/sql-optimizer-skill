"""Progress tracking for SQL Optimizer pipeline stages.

This module provides progress tracking functionality for monitoring
the execution status of pipeline stages.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable

# Valid status values for stages
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

VALID_STATUSES = {STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED}


@dataclass
class StageProgress:
    """Progress information for a single pipeline stage.

    Attributes:
        stage_name: Name of the pipeline stage.
        status: Current status (pending, running, completed, failed).
        started_at: ISO timestamp when stage started, or None.
        completed_at: ISO timestamp when stage completed, or None.
        error: Error message if stage failed, or None.
    """

    stage_name: str
    status: str = STATUS_PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate status after initialization."""
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of: {VALID_STATUSES}")


class ProgressTracker:
    """Tracks progress across multiple pipeline stages.

    Supports callback notifications for progress updates and JSON
    serialization for persistence.

    Attributes:
        run_id: Unique identifier for this pipeline run.
        stages: Dictionary mapping stage names to their progress.
    """

    def __init__(
        self,
        run_id: str,
        callback: Callable[[str, StageProgress], None] | None = None,
    ) -> None:
        """Initialize progress tracker.

        Args:
            run_id: Unique identifier for this pipeline run.
            callback: Optional callback function(stage_name, progress)
                called on each status update.
        """
        self.run_id = run_id
        self.stages: dict[str, StageProgress] = {}
        self._callback: Callable[[str, StageProgress], None] | None = callback

    def _notify_callback(self, stage_name: str, progress: StageProgress) -> None:
        """Invoke callback if registered."""
        if self._callback is not None:
            self._callback(stage_name, progress)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()

    def register_stage(self, stage_name: str) -> None:
        """Register a new stage with pending status.

        Args:
            stage_name: Name of the stage to register.
        """
        if stage_name not in self.stages:
            self.stages[stage_name] = StageProgress(stage_name=stage_name)

    def start_stage(self, stage_name: str) -> None:
        """Mark a stage as started.

        Args:
            stage_name: Name of the stage to start.

        Raises:
            KeyError: If stage is not registered.
        """
        if stage_name not in self.stages:
            self.stages[stage_name] = StageProgress(stage_name=stage_name)

        stage = self.stages[stage_name]
        stage.status = STATUS_RUNNING
        stage.started_at = self._get_timestamp()
        stage.completed_at = None
        stage.error = None

        self._notify_callback(stage_name, stage)

    def complete_stage(self, stage_name: str) -> None:
        """Mark a stage as completed.

        Args:
            stage_name: Name of the stage to complete.

        Raises:
            KeyError: If stage is not registered.
        """
        if stage_name not in self.stages:
            raise KeyError(f"Stage '{stage_name}' is not registered")

        stage = self.stages[stage_name]
        stage.status = STATUS_COMPLETED
        stage.completed_at = self._get_timestamp()

        self._notify_callback(stage_name, stage)

    def fail_stage(self, stage_name: str, error: str) -> None:
        """Mark a stage as failed.

        Args:
            stage_name: Name of the stage that failed.
            error: Error message describing the failure.

        Raises:
            KeyError: If stage is not registered.
        """
        if stage_name not in self.stages:
            raise KeyError(f"Stage '{stage_name}' is not registered")

        stage = self.stages[stage_name]
        stage.status = STATUS_FAILED
        stage.completed_at = self._get_timestamp()
        stage.error = error

        self._notify_callback(stage_name, stage)

    def get_status(self) -> dict[str, Any]:
        """Get overall status as dictionary.

        Returns:
            Dictionary containing run_id and all stage progress.
        """
        stages_data: dict[str, Any] = {
            name: asdict(progress) for name, progress in self.stages.items()
        }
        return {
            "run_id": self.run_id,
            "stages": stages_data,
        }

    def to_json(self) -> str:
        """Serialize tracker state to JSON string.

        Returns:
            JSON string representation of the tracker.
        """
        return json.dumps(self.get_status(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(
        cls,
        json_str: str,
        callback: Callable[[str, StageProgress], None] | None = None,
    ) -> "ProgressTracker":
        """Deserialize tracker from JSON string.

        Args:
            json_str: JSON string to deserialize.
            callback: Optional callback for future progress updates.

        Returns:
            Reconstructed ProgressTracker instance.

        Raises:
            json.JSONDecodeError: If JSON is invalid.
            KeyError: If required fields are missing.
        """
        data = json.loads(json_str)

        tracker = cls(run_id=data["run_id"], callback=callback)

        for stage_name, stage_data in data.get("stages", {}).items():
            tracker.stages[stage_name] = StageProgress(
                stage_name=stage_data["stage_name"],
                status=stage_data["status"],
                started_at=stage_data.get("started_at"),
                completed_at=stage_data.get("completed_at"),
                error=stage_data.get("error"),
            )

        return tracker
