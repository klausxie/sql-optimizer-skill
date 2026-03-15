"""Progress reporting utilities for CLI output."""

from __future__ import annotations

import os
import sys
from typing import TextIO


def _supports_unicode(output: TextIO) -> bool:
    encoding = str(getattr(output, "encoding", "") or "").lower()
    if "utf-8" in encoding or "utf8" in encoding:
        return True
    if os.name != "nt":
        return True
    return False


class ProgressReporter:
    """Reports progress information to stderr for human readability."""

    def __init__(self, enabled: bool = True, output: TextIO = sys.stderr):
        self.enabled = enabled
        self.output = output
        if _supports_unicode(output):
            self._prefixes = {
                "phase_start": "▶",
                "phase_complete": "✓",
                "info": "i",
                "warn": "!",
            }
        else:
            self._prefixes = {
                "phase_start": ">",
                "phase_complete": "[ok]",
                "info": "[i]",
                "warn": "[warn]",
            }

    def report_phase_start(self, phase: str, description: str = "") -> None:
        if not self.enabled:
            return
        msg = f"{self._prefixes['phase_start']} start phase: {phase}"
        if description:
            msg += f" - {description}"
        self._write(msg)

    def report_phase_complete(self, phase: str) -> None:
        if not self.enabled:
            return
        self._write(f"{self._prefixes['phase_complete']} phase complete: {phase}")

    def report_statement_progress(self, current: int, total: int, sql_key: str = "") -> None:
        if not self.enabled:
            return
        msg = f"  statement {current}/{total}"
        if sql_key:
            msg += f" ({sql_key})"
        self._write(msg)

    def report_info(self, message: str) -> None:
        if not self.enabled:
            return
        self._write(f"{self._prefixes['info']} {message}")

    def report_warning(self, message: str) -> None:
        if not self.enabled:
            return
        self._write(f"{self._prefixes['warn']} {message}")

    def _write(self, message: str) -> None:
        self.output.write(message + "\n")
        self.output.flush()


_progress_reporter: ProgressReporter | None = None


def init_progress_reporter(enabled: bool = True) -> ProgressReporter:
    global _progress_reporter
    _progress_reporter = ProgressReporter(enabled=enabled)
    return _progress_reporter


def get_progress_reporter() -> ProgressReporter:
    global _progress_reporter
    if _progress_reporter is None:
        _progress_reporter = ProgressReporter(enabled=False)
    return _progress_reporter
