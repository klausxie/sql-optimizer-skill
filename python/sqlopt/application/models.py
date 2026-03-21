from __future__ import annotations

from typing import Any, Literal, TypedDict


StageStatusMap = dict[str, str]
StatementStageState = dict[str, str]


class RunState(TypedDict, total=False):
    current_stage: str
    stage_status: StageStatusMap
    statements: dict[str, StatementStageState]
    attempts_by_stage: dict[str, int]
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
