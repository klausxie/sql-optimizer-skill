from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from .models import ResolvedConfig, RunMeta, RunPlan, RunState

RunRepository = Any  # type: ignore


@dataclass(frozen=True)
class AdvanceStepRequest:
    run_dir: Path
    config: ResolvedConfig
    to_stage: str
    validator: ContractValidator
    repository: RunRepository | None = None


@dataclass(frozen=True)
class RunStatusRequest:
    run_id: str
    state: RunState
    plan: RunPlan
    meta: RunMeta
    config: ResolvedConfig
