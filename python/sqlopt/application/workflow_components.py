from __future__ import annotations

from typing import Any, Callable

from .finalizer import RunFinalizer
from .status_resolver import PhaseExecutionPolicy, StatusResolver


def build_status_resolver(
    *,
    stage_order: list[str],
    phase_policies: dict[str, PhaseExecutionPolicy],
) -> StatusResolver:
    return StatusResolver(stage_order=stage_order, phase_policies=phase_policies)


def build_run_finalizer(
    *,
    report_enabled: Callable[[dict[str, Any]], bool],
    report_generate: Callable[..., object],
) -> RunFinalizer:
    return RunFinalizer(
        report_enabled=report_enabled,
        report_generate=report_generate,
    )
