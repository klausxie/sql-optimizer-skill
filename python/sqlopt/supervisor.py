from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CONTRACT_VERSION, SKILL_VERSION
from .io_utils import append_jsonl, read_json, write_json
from .run_paths import RunPaths, canonical_paths

PHASES = ["scan", "optimize", "validate", "patch_generate", "report"]


def get_run_paths(run_dir: Path) -> RunPaths:
    return canonical_paths(run_dir)


def init_run(run_dir: Path, config: dict[str, Any], run_id: str) -> None:
    p = get_run_paths(run_dir)
    p.ensure_layout()

    write_json(
        p.supervisor_dir / "meta.json",
        {
            "run_id": run_id,
            "status": "RUNNING",
            "contract_version": CONTRACT_VERSION,
            "skill_version": SKILL_VERSION,
            "config_version": config.get("config_version", "v1"),
        },
    )
    write_json(
        p.supervisor_dir / "plan.json",
        {"phases": PHASES, "to_stage": "patch_generate", "sql_keys": []},
    )
    write_json(
        p.supervisor_dir / "state.json",
        {
            "current_phase": "scan",
            "phase_status": {k: "PENDING" for k in PHASES},
            "statements": {},
            "attempts_by_phase": {k: 0 for k in PHASES},
            "report_rebuild_required": False,
            "last_error": None,
            "last_reason_code": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def load_state(run_dir: Path) -> dict[str, Any]:
    return read_json(get_run_paths(run_dir).state_path)


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    write_json(get_run_paths(run_dir).state_path, state)


def set_plan(run_dir: Path, plan: dict[str, Any]) -> None:
    write_json(get_run_paths(run_dir).plan_path, plan)


def get_plan(run_dir: Path) -> dict[str, Any]:
    return read_json(get_run_paths(run_dir).plan_path)


def load_meta(run_dir: Path) -> dict[str, Any]:
    return read_json(get_run_paths(run_dir).meta_path)


def save_meta(run_dir: Path, meta: dict[str, Any]) -> None:
    write_json(get_run_paths(run_dir).meta_path, meta)


def set_meta_status(run_dir: Path, status: str) -> None:
    meta = load_meta(run_dir)
    meta["status"] = status
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_meta(run_dir, meta)


def append_step_result(
    run_dir: Path,
    phase: str,
    status: str,
    *,
    sql_key: str | None = None,
    reason_code: str | None = None,
    artifact_refs: list[str] | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    append_jsonl(
        get_run_paths(run_dir).supervisor_result_path(phase),
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "status": status,
            "sql_key": sql_key,
            "reason_code": reason_code,
            "artifact_refs": artifact_refs or [],
            "detail": detail or {},
        },
    )
