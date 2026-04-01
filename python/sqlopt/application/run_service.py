from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from ..config import load_config
from ..contracts import ContractValidator
from ..manifest import log_event
from ..run_paths import canonical_paths
from ..stages import apply as apply_stage
from . import run_index, workflow_engine
from .run_selection import apply_selection_to_config, normalize_run_selection, selection_matches
from .lifecycle_policy import LifecycleOutcome
from . import lifecycle_policy
from .requests import AdvanceStepRequest, RunStatusRequest
from .run_repository import RunRepository


def start_run(
    config_path: Path,
    to_stage: str,
    run_id: str | None,
    *,
    repo_root: Path,
    selection: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    config = load_config(config_path)
    project_root = Path(str((config.get("project", {}) or {}).get("root_path") or ".")).resolve()
    normalized_selection = normalize_run_selection(
        project_root=project_root,
        mapper_paths=list((selection or {}).get("mapper_paths") or []),
        sql_keys=list((selection or {}).get("sql_keys") or []),
    )
    config = apply_selection_to_config(config, normalized_selection)
    resolved_run_id = run_id or f"run_{uuid4().hex[:12]}"
    runs_root = workflow_engine.runs_root(config)
    run_dir = runs_root / resolved_run_id
    repository = RunRepository(run_dir)
    if not run_dir.exists():
        # resolved_config is now stored in plan.json by init_run
        repository.initialize(config, resolved_run_id)
        log_event(canonical_paths(run_dir).manifest_path, "initialize", "done", {"run_id": resolved_run_id})
    run_index.remember_run(resolved_run_id, run_dir, config_path, runs_root)
    repository.set_meta_status("RUNNING")

    plan = repository.get_plan()
    plan["to_stage"] = to_stage
    existing_selection = dict(plan.get("selection") or {}) if isinstance(plan.get("selection"), dict) else None
    if existing_selection:
        if normalized_selection is not None and not selection_matches(existing_selection, normalized_selection):
            raise ValueError("run selection does not match the existing run plan")
    elif normalized_selection:
        plan["selection"] = normalized_selection
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
    repository = RunRepository(run_dir)
    # Load resolved config from plan.json instead of overview/config.resolved.json
    plan = repository.get_plan()
    config = plan.get("resolved_config") or {}
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
    # Load resolved config from plan.json instead of overview/config.resolved.json
    config = plan.get("resolved_config") or {}
    return workflow_engine.build_status_snapshot(
        RunStatusRequest(
            run_id=run_id,
            state=state,
            plan=plan,
            meta=state,  # meta info is now in state.json
            config=config,
        )
    )


def apply_run(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    state = apply_stage.apply_from_config(run_dir)
    return {"run_id": run_id, "apply": state}


def advance_run_until_complete(
    run_id: str,
    initial_result: dict[str, Any],
    *,
    step_fn: Callable[[], dict[str, Any]],
    max_steps: int,
    max_seconds: int,
) -> LifecycleOutcome:
    # Keep run_id in signature so call sites stay explicit about lifecycle ownership.
    return lifecycle_policy.advance_until_complete(
        initial_result,
        step_fn=step_fn,
        max_steps=max_steps,
        max_seconds=max_seconds,
    )


def build_progress_payload(run_id: str, outcome: LifecycleOutcome) -> dict[str, Any]:
    return lifecycle_policy.build_progress_payload(run_id, outcome)


def build_interrupt_payload(run_id: str, *, next_action: str | None = None) -> dict[str, Any]:
    return lifecycle_policy.build_interrupt_payload(run_id, next_action=next_action)


def status_requires_report_rebuild(status_snapshot: dict[str, Any]) -> bool:
    return lifecycle_policy.status_requires_report_rebuild(status_snapshot)
