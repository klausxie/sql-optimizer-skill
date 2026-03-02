from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CONTRACT_VERSION, SKILL_VERSION
from .io_utils import append_jsonl, ensure_dir, read_json, write_json

PHASES = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]


@dataclass
class RunPaths:
    run_dir: Path
    supervisor_dir: Path
    manifest_path: Path
    scan_path: Path
    proposals_path: Path
    acceptance_path: Path
    patches_path: Path
    report_json_path: Path


def get_run_paths(run_dir: Path) -> RunPaths:
    return RunPaths(
        run_dir=run_dir,
        supervisor_dir=run_dir / "supervisor",
        manifest_path=run_dir / "manifest.jsonl",
        scan_path=run_dir / "scan.sqlunits.jsonl",
        proposals_path=run_dir / "proposals" / "optimization.proposals.jsonl",
        acceptance_path=run_dir / "acceptance" / "acceptance.results.jsonl",
        patches_path=run_dir / "patches" / "patch.results.jsonl",
        report_json_path=run_dir / "report.json",
    )


def init_run(run_dir: Path, config: dict[str, Any], run_id: str) -> None:
    p = get_run_paths(run_dir)
    ensure_dir(p.run_dir)
    ensure_dir(p.supervisor_dir)
    ensure_dir(p.run_dir / "supervisor" / "results")
    ensure_dir(p.run_dir / "proposals")
    ensure_dir(p.run_dir / "acceptance")
    ensure_dir(p.run_dir / "patches")
    ensure_dir(p.run_dir / "ops")

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
    write_json(p.supervisor_dir / "plan.json", {"phases": PHASES, "to_stage": "patch_generate", "sql_keys": []})
    write_json(
        p.supervisor_dir / "state.json",
        {
            "current_phase": "preflight",
            "phase_status": {k: "PENDING" for k in PHASES},
            "statements": {},
            "attempts_by_phase": {k: 0 for k in PHASES},
            "last_error": None,
            "last_reason_code": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def load_state(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / "supervisor" / "state.json")


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    write_json(run_dir / "supervisor" / "state.json", state)


def set_plan(run_dir: Path, plan: dict[str, Any]) -> None:
    write_json(run_dir / "supervisor" / "plan.json", plan)


def get_plan(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / "supervisor" / "plan.json")


def load_meta(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / "supervisor" / "meta.json")


def save_meta(run_dir: Path, meta: dict[str, Any]) -> None:
    write_json(run_dir / "supervisor" / "meta.json", meta)


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
        run_dir / "supervisor" / "results" / f"{phase}.jsonl",
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
