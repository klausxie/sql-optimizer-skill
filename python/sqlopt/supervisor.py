from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CONTRACT_VERSION, SKILL_VERSION
from .io_utils import append_jsonl, read_json, write_json
from .run_paths import canonical_paths

PHASES = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]


def init_run(run_dir: Path, config: dict[str, Any], run_id: str) -> None:
    """Initialize a new run with the new minimal layout.

    Layout:
        runs/<run-id>/
        ├── report.json (created later by report stage)
        ├── control/
        │   ├── state.json (replaces both meta.json and state.json)
        │   ├── plan.json
        │   └── manifest.jsonl
        ├── artifacts/
        └── sql/
    """
    p = canonical_paths(run_dir)
    p.ensure_layout()

    # Write state.json - combines former meta.json + state.json
    # This is the single source of truth for run identity and current state
    write_json(
        p.state_path,
        {
            "run_id": run_id,
            "status": "RUNNING",
            "contract_version": CONTRACT_VERSION,
            "skill_version": SKILL_VERSION,
            "config_version": config.get("config_version", "v1"),
            "current_phase": "preflight",
            "phase_status": {k: "PENDING" for k in PHASES},
            "statements": {},
            "attempts_by_phase": {k: 0 for k in PHASES},
            "report_rebuild_required": False,
            "last_error": None,
            "last_reason_code": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Write plan.json - stores the run plan and resolved config
    write_json(
        p.plan_path,
        {
            "phases": PHASES,
            "to_stage": "patch_generate",
            "sql_keys": [],
            "resolved_config": config,  # Store resolved config in plan.json
        },
    )


def load_state(run_dir: Path) -> dict[str, Any]:
    """Load the run state from control/state.json."""
    return read_json(canonical_paths(run_dir).state_path)


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    """Save the run state to control/state.json."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(canonical_paths(run_dir).state_path, state)


def set_plan(run_dir: Path, plan: dict[str, Any]) -> None:
    """Save the run plan to control/plan.json."""
    write_json(canonical_paths(run_dir).plan_path, plan)


def get_plan(run_dir: Path) -> dict[str, Any]:
    """Load the run plan from control/plan.json."""
    return read_json(canonical_paths(run_dir).plan_path)


def set_run_status(run_dir: Path, status: str) -> None:
    """Update the run status in control/state.json."""
    state = load_state(run_dir)
    state["status"] = status
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(run_dir, state)


def append_manifest_event(
    run_dir: Path,
    stage: str,
    event: str,
    *,
    sql_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append an event to the manifest.jsonl in control/.

    This replaces the per-phase supervisor results files.
    """
    append_jsonl(
        canonical_paths(run_dir).manifest_path,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "event": event,
            "sql_key": sql_key,
            "payload": payload or {},
        },
    )


def append_phase_event(
    run_dir: Path,
    phase: str,
    status: str,
    *,
    sql_key: str | None = None,
    reason_code: str | None = None,
    artifact_refs: list[str] | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append a phase event row into control/manifest.jsonl."""
    append_manifest_event(
        run_dir,
        phase,
        str(status or "").strip().lower() or "unknown",
        sql_key=sql_key,
        payload={
            "status": status,
            "reason_code": reason_code,
            "artifact_refs": list(artifact_refs or []),
            "detail": dict(detail or {}),
        },
    )


def set_meta_status(run_dir: Path, status: str) -> None:
    """Legacy alias for set_run_status()."""
    set_run_status(run_dir, status)


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
    """Legacy alias for append_phase_event()."""
    append_phase_event(
        run_dir,
        phase,
        status,
        sql_key=sql_key,
        reason_code=reason_code,
        artifact_refs=artifact_refs,
        detail=detail,
    )
