"""Progress reporting utilities for CLI output."""

from __future__ import annotations

import sys
from typing import TextIO


class ProgressReporter:
    """Reports progress information to stderr for human readability."""

    def __init__(self, enabled: bool = True, output: TextIO = sys.stderr):
        """Initialize progress reporter.

        Args:
            enabled: Whether progress reporting is enabled
            output: Output stream for progress messages (default: stderr)
        """
        self.enabled = enabled
        self.output = output

    def report_phase_start(self, phase: str, description: str = "") -> None:
        """Report the start of a phase.

        Args:
            phase: Phase name
            description: Optional description
        """
        if not self.enabled:
            return
        msg = f"▶ Starting phase: {phase}"
        if description:
            msg += f" - {description}"
        self._write(msg)

    def report_phase_complete(self, phase: str) -> None:
        """Report phase completion.

        Args:
            phase: Phase name
        """
        if not self.enabled:
            return
        self._write(f"✓ Completed phase: {phase}")

    def report_statement_progress(self, current: int, total: int, sql_key: str = "") -> None:
        """Report progress on statement processing.

        Args:
            current: Current statement number (1-indexed)
            total: Total number of statements
            sql_key: Optional SQL key being processed
        """
        if not self.enabled:
            return
        msg = f"  Processing statement {current}/{total}"
        if sql_key:
            msg += f" ({sql_key})"
        self._write(msg)

    def report_info(self, message: str) -> None:
        """Report informational message.

        Args:
            message: Message to report
        """
        if not self.enabled:
            return
        self._write(f"ℹ {message}")

    def report_warning(self, message: str) -> None:
        """Report warning message.

        Args:
            message: Warning message
        """
        if not self.enabled:
            return
        self._write(f"⚠ {message}")

    def _write(self, message: str) -> None:
        """Write message to output stream.

        Args:
            message: Message to write
        """
        self.output.write(message + "\n")
        self.output.flush()


# Global progress reporter instance
_progress_reporter: ProgressReporter | None = None


def init_progress_reporter(enabled: bool = True) -> ProgressReporter:
    """Initialize the global progress reporter.

    Args:
        enabled: Whether progress reporting is enabled

    Returns:
        The initialized progress reporter
    """
    global _progress_reporter
    _progress_reporter = ProgressReporter(enabled=enabled)
    return _progress_reporter


def get_progress_reporter() -> ProgressReporter:
    """Get the global progress reporter.

    Returns:
        The global progress reporter, or a disabled one if not initialized
    """
    global _progress_reporter
    if _progress_reporter is None:
        _progress_reporter = ProgressReporter(enabled=False)
    return _progress_reporter
