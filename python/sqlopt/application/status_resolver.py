from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .requests import RunStatusRequest


@dataclass(frozen=True)
class PhaseExecutionPolicy:
    phase: str
    allow_regenerate: bool = False


@dataclass(frozen=True)
class ResumeDecision:
    phase: str
    final_meta_status: str


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
        counts = {"optimize": 0, "validate": 0, "patch_generate": 0}
        for phases in state.get("statements", {}).values():
            for phase in counts:
                if phases.get(phase) == "PENDING":
                    counts[phase] += 1
        return counts

    def report_enabled(self, config: dict[str, Any]) -> bool:
        return bool((config.get("report", {}) or {}).get("enabled", True))

    def _report_required_for_target(self, to_stage: str) -> bool:
        return str(to_stage or "").strip() in {"patch_generate", "report"}

    def report_rebuild_required(self, state: dict[str, Any]) -> bool:
        return bool(state.get("report_rebuild_required", False))

    def is_complete_to_stage(self, state: dict[str, Any], to_stage: str, *, include_report: bool = False) -> bool:
        target = "report" if include_report else to_stage
        for phase in self.stage_order:
            status = state.get("phase_status", {}).get(phase)
            if phase == target:
                return status == "DONE"
            if status not in {"DONE", "SKIPPED"}:
                return False
        return False

    def resolve_report_resume_decision(
        self,
        state: dict[str, Any],
        to_stage: str,
        config: dict[str, Any],
    ) -> ResumeDecision | None:
        if not self._report_required_for_target(to_stage):
            return None
        report_policy = self.phase_policies["report"]
        report_status = state.get("phase_status", {}).get("report")
        report_needs_work = report_status != "DONE" or self.report_rebuild_required(state)
        if self.report_enabled(config):
            if to_stage == "report" and report_policy.allow_regenerate:
                if not self.is_complete_to_stage(state, "patch_generate", include_report=False):
                    return None
                return ResumeDecision(phase="report", final_meta_status="COMPLETED")
            if self.is_complete_to_stage(state, to_stage, include_report=False):
                if report_needs_work:
                    return ResumeDecision(phase="report", final_meta_status="COMPLETED")
            return None

        if to_stage == "report":
            if not self.is_complete_to_stage(state, "patch_generate", include_report=False):
                return None
            return ResumeDecision(phase="report", final_meta_status="COMPLETED")
        if self.is_complete_to_stage(state, to_stage, include_report=False) and state.get("phase_status", {}).get("report") != "SKIPPED":
            return ResumeDecision(phase="report", final_meta_status="COMPLETED")
        return None

    def resolve_status(self, request: RunStatusRequest) -> StatusResolution:
        report_on = self.report_enabled(request.config)
        report_status = request.state.get("phase_status", {}).get("report")
        target_stage = request.plan.get("to_stage", "patch_generate")
        report_required = report_on and self._report_required_for_target(target_stage)
        report_resume = self.resolve_report_resume_decision(request.state, target_stage, request.config)
        base_complete = self.is_complete_to_stage(request.state, target_stage, include_report=False)
        report_rebuild = self.report_rebuild_required(request.state)
        report_done = report_status == "DONE"
        complete = base_complete or (
            report_required and report_done and report_rebuild and request.meta.get("status") == "COMPLETED"
        )
        if report_required and report_resume is None and base_complete and (target_stage == "report" or report_done):
            complete = True
        elif report_required and report_resume is not None and not base_complete:
            complete = False
        if not report_on and report_resume is not None and not base_complete:
            complete = False

        current_phase = request.state.get("current_phase")
        if isinstance(current_phase, str) and current_phase in {"optimize", "validate", "patch_generate"} and not complete:
            current_sql_key = self.next_pending_sql(request.state, current_phase)
        else:
            current_sql_key = None

        report_action_required = report_resume is not None
        if report_required and target_stage == "report":
            report_action_required = self.is_complete_to_stage(request.state, "patch_generate", include_report=False) and (
                report_status != "DONE" or report_rebuild
            )

        if report_action_required:
            if report_on and (report_rebuild or report_status != "DONE"):
                next_action = "report-rebuild"
            elif not report_on:
                next_action = "resume"
            else:
                next_action = "report-rebuild"
        elif not complete:
            next_action = "resume"
        else:
            next_action = "none"

        return StatusResolution(complete=complete, next_action=next_action, current_sql_key=current_sql_key)

    def report_phase_complete_for_result(self, state: dict[str, Any], to_stage: str, config: dict[str, Any]) -> bool:
        if self.report_enabled(config) and self._report_required_for_target(to_stage):
            return self.is_complete_to_stage(state, to_stage, include_report=True)
        return self.is_complete_to_stage(state, to_stage, include_report=False)
