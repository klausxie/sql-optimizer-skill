from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .models import HarnessHooks, HarnessRunResult
from .runner import run_once, resume_once, status_once

_TERMINAL_PHASE_STATUSES = {"DONE", "SKIPPED", "FAILED"}


def _build_run_result(
    *,
    run_id: str,
    run_dir: Path,
    status: dict[str, Any],
    steps: int,
    started: float,
    first_step: dict[str, Any],
) -> HarnessRunResult:
    return HarnessRunResult(
        run_id=run_id,
        run_dir=run_dir,
        status=status,
        steps=steps,
        elapsed_seconds=time.monotonic() - started,
        first_step=first_step,
    )


def _phase_terminal(status: dict[str, Any], phase: str) -> bool:
    phase_status = status.get("phase_status") or {}
    return str(phase_status.get(phase) or "").upper() in _TERMINAL_PHASE_STATUSES


def run_until_complete(
    *,
    config_path: Path,
    to_stage: str,
    run_id: str,
    repo_root: Path,
    selection: dict[str, Any] | None = None,
    max_steps: int = 1000,
    hooks: HarnessHooks | None = None,
) -> HarnessRunResult:
    started = time.monotonic()
    first = run_once(
        config_path=config_path,
        to_stage=to_stage,
        run_id=run_id,
        repo_root=repo_root,
        selection=selection,
        hooks=hooks,
    )
    steps = 1
    status = status_once(run_id=first.run_id, repo_root=repo_root)
    if status.get("complete"):
        return _build_run_result(
            run_id=first.run_id,
            run_dir=first.run_dir,
            status=status,
            steps=steps,
            started=started,
            first_step=first.result,
        )

    for _ in range(max_steps - 1):
        step = resume_once(run_id=first.run_id, repo_root=repo_root, hooks=hooks)
        steps += 1
        status = status_once(run_id=step.run_id, repo_root=repo_root)
        if status.get("complete"):
            return _build_run_result(
                run_id=step.run_id,
                run_dir=step.run_dir,
                status=status,
                steps=steps,
                started=started,
                first_step=first.result,
            )

    raise AssertionError("run did not complete within expected loop budget")


def run_until_stage_complete(
    *,
    config_path: Path,
    to_stage: str,
    run_id: str,
    repo_root: Path,
    selection: dict[str, Any] | None = None,
    max_steps: int = 1000,
    hooks: HarnessHooks | None = None,
) -> HarnessRunResult:
    started = time.monotonic()
    first = run_once(
        config_path=config_path,
        to_stage=to_stage,
        run_id=run_id,
        repo_root=repo_root,
        selection=selection,
        hooks=hooks,
    )
    steps = 1
    status = status_once(run_id=first.run_id, repo_root=repo_root)
    if status.get("complete") or _phase_terminal(status, to_stage):
        return _build_run_result(
            run_id=first.run_id,
            run_dir=first.run_dir,
            status=status,
            steps=steps,
            started=started,
            first_step=first.result,
        )

    for _ in range(max_steps - 1):
        step = resume_once(run_id=first.run_id, repo_root=repo_root, hooks=hooks)
        steps += 1
        status = status_once(run_id=step.run_id, repo_root=repo_root)
        if status.get("complete") or _phase_terminal(status, to_stage):
            return _build_run_result(
                run_id=step.run_id,
                run_dir=step.run_dir,
                status=status,
                steps=steps,
                started=started,
                first_step=first.result,
            )

    raise AssertionError(f"run did not reach terminal status for phase {to_stage!r} within expected loop budget")
