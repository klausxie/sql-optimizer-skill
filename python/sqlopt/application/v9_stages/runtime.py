from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ...contracts import ContractValidator
from ...v9_pipeline import STAGE_ORDER, require_v9_stage

StageRunner = Callable[[Path], dict[str, Any]]
StageImplementation = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class V9StageSpec:
    name: str
    runner: StageImplementation

    def bind(
        self,
        *,
        config: dict[str, Any],
        validator: ContractValidator,
    ) -> StageRunner:
        return lambda run_dir: self.runner(
            run_dir,
            config=config,
            validator=validator,
        )


# Deferred imports at module scope are fine here because stage modules are lightweight.
from .init import run_init
from .optimize import run_optimize
from .parse import run_parse
from .patch import run_patch
from .recognition import run_recognition

_STAGE_SPECS = {
    spec.name: spec
    for spec in (
        V9StageSpec("init", run_init),
        V9StageSpec("parse", run_parse),
        V9StageSpec("recognition", run_recognition),
        V9StageSpec("optimize", run_optimize),
        V9StageSpec("patch", run_patch),
    )
}


def get_stage_spec(stage_name: str) -> V9StageSpec:
    normalized = require_v9_stage(stage_name)
    try:
        return _STAGE_SPECS[normalized]
    except KeyError as exc:
        raise ValueError(f"unregistered V9 stage '{normalized}'") from exc


def build_stage_registry(
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, StageRunner]:
    return {
        stage_name: get_stage_spec(stage_name).bind(
            config=config,
            validator=validator,
        )
        for stage_name in STAGE_ORDER
    }


def run_stage(
    stage_name: str,
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    return get_stage_spec(stage_name).bind(config=config, validator=validator)(run_dir)
