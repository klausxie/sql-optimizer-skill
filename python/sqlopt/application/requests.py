from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from .models import ResolvedConfig, RunMeta, RunPlan, RunState
from .run_repository import RunRepository

RunPhaseAction = Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]


@dataclass(frozen=True)
class AdvanceStepRequest:
    run_dir: Path
    config: ResolvedConfig
    to_stage: str
    validator: ContractValidator
    repository: RunRepository | None = None
    run_phase_action_fn: RunPhaseAction | None = None
    record_failure_fn: RecordFailure | None = None
    finalize_report_if_enabled_fn: Callable[..., bool] | None = None
    finalize_without_report_fn: Callable[..., None] | None = None


@dataclass(frozen=True)
class RunStatusRequest:
    run_id: str
    state: RunState
    plan: RunPlan
    meta: RunMeta
    config: ResolvedConfig
