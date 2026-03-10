from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from ..failure_classification import classify_reason_code

_BUDGET_EXHAUSTION_REASONS = {
    "step_budget_exhausted",
    "time_budget_exhausted",
}


@dataclass(frozen=True)
class LifecycleOutcome:
    result: dict[str, Any]
    steps_executed: int
    reason: str
    complete: bool
    retryable: bool


def is_retryable_reason(reason_code: str | None) -> bool:
    code = str(reason_code or "").strip()
    if not code:
        return False
    if code in _BUDGET_EXHAUSTION_REASONS:
        return True
    return classify_reason_code(code) == "retryable"


def status_requires_report_rebuild(status_snapshot: dict[str, Any]) -> bool:
    return str(status_snapshot.get("next_action") or "") == "report-rebuild"


def advance_until_complete(
    initial_result: dict[str, Any],
    *,
    step_fn: Callable[[], dict[str, Any]],
    max_steps: int,
    max_seconds: int,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> LifecycleOutcome:
    """Advance run state until completion or budget exhaustion.

    max_steps=0 and max_seconds=0 mean unbounded.
    """
    start_ts = monotonic_fn()
    steps_executed = 1
    result = initial_result

    while not bool(result.get("complete", False)):
        if max_steps > 0 and steps_executed >= max_steps:
            reason = "step_budget_exhausted"
            return LifecycleOutcome(
                result=result,
                steps_executed=steps_executed,
                reason=reason,
                complete=False,
                retryable=is_retryable_reason(reason),
            )
        elapsed = monotonic_fn() - start_ts
        if max_seconds > 0 and elapsed >= max_seconds:
            reason = "time_budget_exhausted"
            return LifecycleOutcome(
                result=result,
                steps_executed=steps_executed,
                reason=reason,
                complete=False,
                retryable=is_retryable_reason(reason),
            )
        result = step_fn()
        steps_executed += 1

    return LifecycleOutcome(
        result=result,
        steps_executed=steps_executed,
        reason="completed",
        complete=True,
        retryable=False,
    )


def build_progress_payload(run_id: str, outcome: LifecycleOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "result": outcome.result,
        "steps_executed": outcome.steps_executed,
        "complete": outcome.complete,
    }
    if outcome.reason != "completed":
        payload["retryable"] = outcome.retryable
        payload["reason"] = outcome.reason
    return payload


def build_interrupt_payload(run_id: str, *, next_action: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "interrupted": True,
        "retryable": True,
        "message": "Interrupted by user (Ctrl+C)",
    }
    if next_action:
        payload["next_action"] = next_action
    return payload
