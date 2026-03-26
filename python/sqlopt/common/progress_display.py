"""Progress display utility for SQL Optimizer pipeline.

Provides user-friendly progress output without external dependencies.
Supports TTY (in-place update) and non-TTY (simple print) modes.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass


@dataclass
class ProgressDisplay:
    """Text-based progress display for pipeline stages.

    In TTY mode: updates line in-place with progress bar.
    In non-TTY mode: prints simple progress lines.

    Usage:
        display = ProgressDisplay()
        display.update("init", 1, 5, "Processing file 3/47")
        display.finish("init", 2.3)  # Prints: "✅ Init (2.3s)"
    """

    total_stages: int = 5
    _start_time: float | None = None
    _current_stage: str | None = None

    def __post_init__(self) -> None:
        self._is_tty = sys.stdout.isatty()
        self._stage_start: dict[str, float] = {}

    def _truncate(self, text: str, max_len: int = 60) -> str:
        """Truncate text to fit terminal width."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _render_bar(self, current: int, total: int, width: int = 10) -> str:
        """Render ASCII progress bar."""
        if total <= 0:
            return "░" * width
        filled = int(width * current / total)
        return "█" * filled + "░" * (width - filled)

    def update(
        self,
        stage: str,
        stage_idx: int,
        message: str = "",
    ) -> None:
        """Update progress display.

        Args:
            stage: Current stage name (e.g., "init", "parse")
            stage_idx: Current stage index (1-based, e.g., 2 for stage 2 of 5)
            message: Optional message to display (e.g., "Processing SQL 3/47")
        """
        if self._current_stage != stage:
            self._current_stage = stage
            self._stage_start[stage] = time.time()

        # Calculate overall progress (stage_idx is 1-based)
        overall_pct = stage_idx * 100 // self.total_stages
        bar = self._render_bar(stage_idx, self.total_stages)

        # Build output line
        stage_label = stage.upper()
        parts = [f"[{stage_idx}/{self.total_stages}]", stage_label, bar, f"{overall_pct}%"]
        if message:
            parts.append(f"— {self._truncate(message)}")

        line = "  ".join(parts)

        if self._is_tty:
            # In-place update with carriage return
            sys.stdout.write(f"\r{line}")
            sys.stdout.flush()
        else:
            # Simple print for non-TTY (piped to file)
            print(line)

    def finish(self, stage: str, elapsed_seconds: float | None = None) -> None:
        """Print completion message.

        Args:
            stage: Stage name that completed
            elapsed_seconds: Optional elapsed time (if None, calculates from start)
        """
        if elapsed_seconds is None and stage in self._stage_start:
            elapsed_seconds = time.time() - self._stage_start[stage]

        stage_label = stage.upper()
        if elapsed_seconds is not None:
            msg = f"✅ {stage_label} ({elapsed_seconds:.1f}s)"
        else:
            msg = f"✅ {stage_label}"

        if self._is_tty:
            # Clear the progress line and print completion
            sys.stdout.write(f"\r{msg}\n")
            sys.stdout.flush()
        else:
            print(msg)

    def start_pipeline(self, run_id: str) -> None:
        """Print pipeline start message."""
        print(f"\n{'=' * 60}")
        print(f"SQL Optimizer Pipeline — Run: {run_id}")
        print(f"{'=' * 60}\n")

    def finish_pipeline(self, success: bool = True, elapsed: float | None = None) -> None:
        """Print pipeline completion message."""
        print()
        if success:
            msg = "🎉 Pipeline completed successfully"
            if elapsed is not None:
                msg += f" ({elapsed:.1f}s)"
        else:
            msg = "❌ Pipeline failed"
        print(msg)
        print(f"{'=' * 60}\n")
