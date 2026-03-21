from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .requests import RunStatusRequest


@dataclass(frozen=True)
class PhaseExecutionPolicy:
    phase: str
    allow_regenerate: bool = False


@dataclass(frozen=True)
class StatusResolution:
    complete: bool
    next_action: str
    current_sql_key: str | None


class StatusResolver:
    def __init__(
        self,
        *,
        stage_order: list[str],
        phase_policies: dict[str, PhaseExecutionPolicy],
    ) -> None:
        self.stage_order = list(stage_order)
        self.phase_policies = dict(phase_policies)

    def next_pending_sql(self, state: dict[str, Any], phase: str) -> str | None:
        for sql_key, phases in state.get("statements", {}).items():
            if phases.get(phase, "PENDING") == "PENDING":
                return sql_key
        return None

    def pending_by_phase(self, state: dict[str, Any]) -> dict[str, int]:
        counts = {phase: 0 for phase in self.stage_order}
        for phases in state.get("statements", {}).values():
            for phase in counts:
                if phases.get(phase) == "PENDING":
                    counts[phase] += 1
        return counts

    def is_complete_to_stage(
        self, state: dict[str, Any], to_stage: str, *, include_report: bool = False
    ) -> bool:
        del include_report
        for phase in self.stage_order:
            status = state.get("stage_status", {}).get(phase)
            if phase == to_stage:
                return status == "DONE"
            if status not in {"DONE", "SKIPPED"}:
                return False
        return False

    def resolve_status(self, request: RunStatusRequest) -> StatusResolution:
        target_stage = request.plan.get("to_stage", self.stage_order[-1] if self.stage_order else "")
        complete = self.is_complete_to_stage(request.state, target_stage)
        current_stage = request.state.get("current_stage")
        current_sql_key = None
        if (
            isinstance(current_stage, str)
            and current_stage in self.stage_order
            and not complete
        ):
            current_sql_key = self.next_pending_sql(request.state, current_stage)

        return StatusResolution(
            complete=complete,
            next_action="none" if complete else "resume",
            current_sql_key=current_sql_key,
        )

    def report_phase_complete_for_result(
        self, state: dict[str, Any], to_stage: str, config: dict[str, Any]
    ) -> bool:
        del config
        return self.is_complete_to_stage(state, to_stage)
