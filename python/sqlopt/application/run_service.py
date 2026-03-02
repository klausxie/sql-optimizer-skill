from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import load_config
from ..contracts import ContractValidator
from ..manifest import log_event
from ..stages import apply as apply_stage
from . import run_index, workflow_engine
from .requests import AdvanceStepRequest, RunStatusRequest
from .run_repository import RunRepository


def start_run(config_path: Path, to_stage: str, run_id: str | None, *, repo_root: Path) -> tuple[str, dict[str, Any]]:
    config = load_config(config_path)
    resolved_run_id = run_id or f"run_{uuid4().hex[:12]}"
    runs_root = workflow_engine.runs_root(config)
    run_dir = runs_root / resolved_run_id
    repository = RunRepository(run_dir)
    if not run_dir.exists():
        repository.initialize(config, resolved_run_id)
        repository.write_resolved_config(config)
        log_event(run_dir / "manifest.jsonl", "initialize", "done", {"run_id": resolved_run_id})
    run_index.remember_run(resolved_run_id, run_dir, config_path, runs_root)
    repository.set_meta_status("RUNNING")

    plan = repository.get_plan()
    plan["to_stage"] = to_stage
    repository.set_plan(plan)

    validator = ContractValidator(repo_root)
    result = workflow_engine.advance_one_step_request(
        AdvanceStepRequest(
            run_dir=run_dir,
            config=config,
            to_stage=to_stage,
            validator=validator,
            repository=repository,
        )
    )
    return resolved_run_id, result


def resume_run(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    config = load_config(run_dir / "config.resolved.json")
    repository = RunRepository(run_dir)
    plan = repository.get_plan()
    validator = ContractValidator(repo_root)
    return workflow_engine.advance_one_step_request(
        AdvanceStepRequest(
            run_dir=run_dir,
            config=config,
            to_stage=plan.get("to_stage", "patch_generate"),
            validator=validator,
            repository=repository,
        )
    )


def get_status(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    repository = RunRepository(run_dir)
    state = repository.load_state()
    plan = repository.get_plan()
    meta = repository.load_meta()
    config = load_config(run_dir / "config.resolved.json")
    return workflow_engine.build_status_snapshot(
        RunStatusRequest(
            run_id=run_id,
            state=state,
            plan=plan,
            meta=meta,
            config=config,
        )
    )


def apply_run(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    state = apply_stage.apply_from_config(run_dir)
    return {"run_id": run_id, "apply": state}
