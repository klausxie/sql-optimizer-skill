from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HarnessHooks:
    preflight_db_check: dict[str, Any] | None = None


@dataclass(frozen=True)
class HarnessProjectHandle:
    name: str
    root_path: Path
    mutable: bool
    fixture_root: Path


@dataclass(frozen=True)
class HarnessStepResult:
    run_id: str
    run_dir: Path
    result: dict[str, Any]


@dataclass(frozen=True)
class HarnessRunResult:
    run_id: str
    run_dir: Path
    status: dict[str, Any]
    steps: int
    elapsed_seconds: float
    first_step: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessArtifacts:
    run_dir: Path
    report_path: Path
    state_path: Path
    plan_path: Path
    manifest_path: Path
    scan_path: Path
    fragments_path: Path
    proposals_path: Path
    acceptance_path: Path
    patches_path: Path
    sql_catalog_path: Path
    report: dict[str, Any]
    state: dict[str, Any]
    plan: dict[str, Any]
    manifest_rows: list[dict[str, Any]]
    scan_rows: list[dict[str, Any]]
    fragment_rows: list[dict[str, Any]]
    proposal_rows: list[dict[str, Any]]
    acceptance_rows: list[dict[str, Any]]
    patch_rows: list[dict[str, Any]]
    sql_catalog_rows: list[dict[str, Any]]

