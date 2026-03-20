from __future__ import annotations

from typing import Any, Literal, TypedDict


PhaseStatusMap = dict[str, str]
StatementPhaseState = dict[str, str]


class RunState(TypedDict, total=False):
    current_phase: str
    phase_status: PhaseStatusMap
    statements: dict[str, StatementPhaseState]
    attempts_by_phase: dict[str, int]
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
