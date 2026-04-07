from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BenchmarkSnapshot:
    run_id: str
    status: str
    verdict: str
    next_action: str
    phase_status: dict[str, str]
    sql_total: int
    proposal_total: int
    accepted_total: int
    patchable_total: int
    patched_total: int
    blocked_total: int
    blocker_family_counts: dict[str, int] = field(default_factory=dict)
    patch_strategy_counts: dict[str, int] = field(default_factory=dict)
    dynamic_delivery_class_counts: dict[str, int] = field(default_factory=dict)
    convergence_decision_counts: dict[str, int] = field(default_factory=dict)
    convergence_conflict_reason_counts: dict[str, int] = field(default_factory=dict)
    convergence_shape_family_counts: dict[str, int] = field(default_factory=dict)
    patch_convergence_blocked_count: int = 0
    top_reason_codes: list[dict[str, int | str]] = field(default_factory=list)


@dataclass(frozen=True)
class BenchmarkDelta:
    baseline_run_id: str
    candidate_run_id: str
    sql_total_delta: int
    proposal_total_delta: int
    accepted_total_delta: int
    patchable_total_delta: int
    patched_total_delta: int
    blocked_total_delta: int
    blocker_family_count_deltas: dict[str, int] = field(default_factory=dict)
    patch_strategy_count_deltas: dict[str, int] = field(default_factory=dict)
    dynamic_delivery_class_count_deltas: dict[str, int] = field(default_factory=dict)
    convergence_decision_count_deltas: dict[str, int] = field(default_factory=dict)
    convergence_conflict_reason_count_deltas: dict[str, int] = field(default_factory=dict)
    convergence_shape_family_count_deltas: dict[str, int] = field(default_factory=dict)
    patch_convergence_blocked_count_delta: int = 0
    top_reason_code_deltas: dict[str, int] = field(default_factory=dict)
