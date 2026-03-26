"""Abstract base class for all pipeline stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Generic, TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")

# Progress callback type: (message) -> None
ProgressCallback = Callable[[str], None]


class Stage(ABC, Generic[Input, Output]):
    """Abstract base class for all pipeline stages.

    Type Parameters:
        Input: The input contract type for this stage.
        Output: The output contract type for this stage.

    Attributes:
        name: Stage name (e.g., 'init', 'parse').
        started_at: ISO timestamp when stage started, or None.
        duration_seconds: Duration in seconds, or None if not timed.
    """

    def __init__(self, name: str) -> None:
        """Initialize the stage with a name.

        Args:
            name: Stage identifier (e.g., 'init', 'parse').
        """
        self.name = name
        self.started_at: str | None = None
        self.duration_seconds: float | None = None
        self._start_time: datetime | None = None

    def start(self) -> None:
        """Mark the stage as started, recording the start time."""
        self.started_at = datetime.now().isoformat()
        self._start_time = datetime.now()

    def stop(self) -> None:
        """Mark the stage as stopped, calculating duration."""
        if self._start_time is not None:
            elapsed = datetime.now() - self._start_time
            self.duration_seconds = elapsed.total_seconds()
            self._start_time = None

    @contextmanager
    def timed_run(self):
        """Context manager for timing stage execution.

        Usage:
            with stage.timed_run():
                result = stage.run(input_data)
        """
        self.start()
        try:
            yield
        finally:
            self.stop()

    @abstractmethod
    def run(
        self,
        input_data: Input,
        progress_callback: ProgressCallback | None = None,
    ) -> Output:
        """Execute the stage with given input.

        Args:
            input_data: Stage input contract.
            progress_callback: Optional callback (message: str) -> None
                called at key progress points for user-friendly display.

        Returns:
            Stage output contract.
        """
        ...

    def validate_input(self, _input_data: Input) -> bool:
        """Validate input before running. Override for custom validation.

        Args:
            _input_data: Stage input contract to validate.

        Returns:
            True if input is valid, False otherwise.
        """
        return True

    def validate_output(self, _output: Output) -> bool:
        """Validate output after running. Override for custom validation.

        Args:
            _output: Stage output contract to validate.

        Returns:
            True if output is valid, False otherwise.
        """
        return True
