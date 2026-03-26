"""Progress display utility for the SQL Optimizer pipeline.

Provides user-friendly progress output without external dependencies.
Supports TTY (in-place update) and non-TTY (simple print) modes.
Falls back to ASCII when the active terminal encoding cannot print
Unicode progress characters.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass


@dataclass
class ProgressDisplay:
    """Text-based progress display for pipeline stages."""

    total_stages: int = 5
    _start_time: float | None = None
    _current_stage: str | None = None

    def __post_init__(self) -> None:
        self._is_tty = sys.stdout.isatty()
        self._stage_start: dict[str, float] = {}
        self._supports_unicode = self._can_encode("█░✓✗🎉•")

    def _can_encode(self, text: str) -> bool:
        """Return whether stdout can safely encode the given text."""
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            text.encode(encoding)
        except UnicodeEncodeError:
            return False
        return True

    def _truncate(self, text: str, max_len: int = 60) -> str:
        """Truncate text to fit terminal width."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _render_bar(self, current: int, total: int, width: int = 10) -> str:
        """Render a progress bar that matches the active terminal encoding."""
        filled_char = "#" if not self._supports_unicode else "█"
        empty_char = "-" if not self._supports_unicode else "░"
        if total <= 0:
            return empty_char * width
        filled = int(width * current / total)
        return filled_char * filled + empty_char * (width - filled)

    def _status_icon(self, success: bool) -> str:
        """Return a compatible status icon."""
        if self._supports_unicode:
            return "✓" if success else "✗"
        return "+" if success else "x"

    def _pipeline_banner(self, success: bool) -> str:
        """Return a compatible pipeline completion banner."""
        if self._supports_unicode:
            return "🎉 Pipeline completed successfully" if success else "✗ Pipeline failed"
        return "Pipeline completed successfully" if success else "Pipeline failed"

    def _message_separator(self) -> str:
        """Return a separator that works in the active terminal encoding."""
        return "•" if self._supports_unicode else "-"

    def _write_line(self, text: str = "") -> None:
        """Write a line to stdout without relying on print()."""
        sys.stdout.write(f"{text}\n")
        sys.stdout.flush()

    def update(
        self,
        stage: str,
        stage_idx: int,
        message: str = "",
        sub_progress: tuple[int, int] | None = None,
    ) -> None:
        """Update progress display."""
        if self._current_stage != stage:
            self._current_stage = stage
            self._stage_start[stage] = time.time()

        if sub_progress is not None:
            current, total = sub_progress
            overall_pct = int((stage_idx - 1 + current / total) * 100 / self.total_stages)
        else:
            overall_pct = (stage_idx - 1) * 100 // self.total_stages

        bar = self._render_bar(overall_pct, 100)
        parts = [f"[{stage_idx}/{self.total_stages}]", stage.upper(), bar, f"{overall_pct}%"]

        if message:
            parts.append(f"{self._message_separator()} {self._truncate(message)}")

        line = "  ".join(parts)

        if self._is_tty:
            sys.stdout.write(f"\r{line}")
            sys.stdout.flush()
        else:
            self._write_line(line)

    def finish(self, stage: str, elapsed_seconds: float | None = None) -> None:
        """Print completion message."""
        if elapsed_seconds is None and stage in self._stage_start:
            elapsed_seconds = time.time() - self._stage_start[stage]

        stage_label = stage.upper()
        if elapsed_seconds is not None:
            msg = f"{self._status_icon(True)} {stage_label} ({elapsed_seconds:.1f}s)"
        else:
            msg = f"{self._status_icon(True)} {stage_label}"

        if self._is_tty:
            sys.stdout.write(f"\r{msg}\n")
            sys.stdout.flush()
        else:
            self._write_line(msg)

    def start_pipeline(self, run_id: str) -> None:
        """Print pipeline start message."""
        self._write_line()
        self._write_line("=" * 60)
        self._write_line(f"SQL Optimizer Pipeline - Run: {run_id}")
        self._write_line(f"{'=' * 60}\n")

    def finish_pipeline(self, success: bool = True, elapsed: float | None = None) -> None:
        """Print pipeline completion message."""
        self._write_line()
        msg = self._pipeline_banner(success)
        if success and elapsed is not None:
            msg += f" ({elapsed:.1f}s)"
        self._write_line(msg)
        self._write_line(f"{'=' * 60}\n")
