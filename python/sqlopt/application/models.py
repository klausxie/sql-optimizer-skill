from __future__ import annotations

from typing import Any, Literal, TypedDict


class PhaseStatusMap(TypedDict):
    diagnose: str
    optimize: str
    validate: str
    apply: str
    report: str


class StatementPhaseState(TypedDict):
    optimize: str
    validate: str
    apply: str


class RunState(TypedDict, total=False):
    current_phase: str
    phase_status: PhaseStatusMap
    statements: dict[str, StatementPhaseState]
    attempts_by_phase: dict[str, int]
    report_rebuild_required: bool
    last_error: str | None
    last_reason_code: str | None
    updated_at: str


class RunPlan(TypedDict, total=False):
    phases: list[str]
    to_stage: str
    sql_keys: list[str]
    selection: dict[str, Any]


class RunMeta(TypedDict, total=False):
    run_id: str
    status: Literal["RUNNING", "READY_TO_FINALIZE", "COMPLETED", "FAILED"]
    contract_version: str
    skill_version: str
    config_version: str
    updated_at: str


class PhaseResult(TypedDict, total=False):
    complete: bool
    phase: str
    sql_key: str


ResolvedConfig = dict[str, Any]
