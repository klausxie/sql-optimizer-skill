"""Tests for ProgressDisplay terminal compatibility."""

from __future__ import annotations

from sqlopt.common.progress_display import ProgressDisplay


class _FakeStdout:
    def __init__(self, encoding: str, is_tty: bool) -> None:
        self.encoding = encoding
        self._is_tty = is_tty
        self.parts: list[str] = []

    def isatty(self) -> bool:
        return self._is_tty

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return "".join(self.parts)


def test_progress_display_falls_back_to_ascii_for_gbk(monkeypatch) -> None:
    fake_stdout = _FakeStdout(encoding="gbk", is_tty=False)
    monkeypatch.setattr("sqlopt.common.progress_display.sys.stdout", fake_stdout)

    display = ProgressDisplay()
    display.start_pipeline("run-1")
    display.update("init", 1, "Scanning mapper files", (4, 4))
    display.finish("init", 1.2)
    display.finish_pipeline(success=True, elapsed=1.2)

    output = fake_stdout.getvalue()
    assert "#" in output
    assert "-" in output
    assert "SQL Optimizer Pipeline - Run: run-1" in output
    assert "Pipeline completed successfully (1.2s)" in output
    assert "█" not in output
    assert "░" not in output
    assert "✓" not in output


def test_progress_display_uses_unicode_when_terminal_supports_it(monkeypatch) -> None:
    fake_stdout = _FakeStdout(encoding="utf-8", is_tty=False)
    monkeypatch.setattr("sqlopt.common.progress_display.sys.stdout", fake_stdout)

    display = ProgressDisplay()
    display.update("parse", 2, "Expanding branches", (2, 5))
    output = fake_stdout.getvalue()

    assert "█" in output or "░" in output
    assert "• Expanding branches" in output


def test_progress_display_throttles_non_tty_updates(monkeypatch) -> None:
    fake_stdout = _FakeStdout(encoding="utf-8", is_tty=False)
    monkeypatch.setattr("sqlopt.common.progress_display.sys.stdout", fake_stdout)

    display = ProgressDisplay(non_tty_emit_interval_seconds=60.0, non_tty_percent_step=50)
    display.update("recognition", 3, "Step 1", (1, 100))
    display.update("recognition", 3, "Step 2", (2, 100))
    display.update("recognition", 3, "Step 3", (100, 100))

    lines = [line for line in fake_stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    assert "Step 1" in lines[0]
    assert "Step 3" in lines[1]
