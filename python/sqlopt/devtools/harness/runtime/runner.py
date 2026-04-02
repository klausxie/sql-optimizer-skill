from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import patch

from ....application import run_service
from .models import HarnessHooks, HarnessStepResult


def _preflight_patch(hooks: HarnessHooks | None):
    if hooks is None or hooks.preflight_db_check is None:
        return nullcontext()
    return patch("sqlopt.stages.preflight.check_db_connectivity", return_value=hooks.preflight_db_check)


def run_once(
    *,
    config_path: Path,
    to_stage: str,
    run_id: str,
    repo_root: Path,
    selection: dict[str, Any] | None = None,
    hooks: HarnessHooks | None = None,
) -> HarnessStepResult:
    with _preflight_patch(hooks):
        resolved_run_id, result = run_service.start_run(
            config_path,
            to_stage,
            run_id,
            repo_root=repo_root,
            selection=selection,
        )
    return HarnessStepResult(
        run_id=resolved_run_id,
        run_dir=repo_root / "runs" / resolved_run_id,
        result=result,
    )


def resume_once(
    *,
    run_id: str,
    repo_root: Path,
    hooks: HarnessHooks | None = None,
) -> HarnessStepResult:
    with _preflight_patch(hooks):
        result = run_service.resume_run(run_id, repo_root=repo_root)
    return HarnessStepResult(
        run_id=run_id,
        run_dir=repo_root / "runs" / run_id,
        result=result,
    )


def status_once(
    *,
    run_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    return run_service.get_status(run_id, repo_root=repo_root)


def apply_once(
    *,
    run_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    return run_service.apply_run(run_id, repo_root=repo_root)

