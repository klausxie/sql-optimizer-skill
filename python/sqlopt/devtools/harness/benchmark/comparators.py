from __future__ import annotations

from .models import BenchmarkDelta, BenchmarkSnapshot


def _diff_counts(baseline: dict[str, int], candidate: dict[str, int]) -> dict[str, int]:
    keys = set(baseline) | set(candidate)
    return {key: int(candidate.get(key) or 0) - int(baseline.get(key) or 0) for key in sorted(keys)}


def _reason_code_counts(rows: list[dict[str, int | str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        counts[code] = int(row.get("count") or 0)
    return counts


def compare_snapshots(baseline: BenchmarkSnapshot, candidate: BenchmarkSnapshot) -> BenchmarkDelta:
    return BenchmarkDelta(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        sql_total_delta=candidate.sql_total - baseline.sql_total,
        proposal_total_delta=candidate.proposal_total - baseline.proposal_total,
        accepted_total_delta=candidate.accepted_total - baseline.accepted_total,
        patchable_total_delta=candidate.patchable_total - baseline.patchable_total,
        patched_total_delta=candidate.patched_total - baseline.patched_total,
        blocked_total_delta=candidate.blocked_total - baseline.blocked_total,
        blocker_family_count_deltas=_diff_counts(baseline.blocker_family_counts, candidate.blocker_family_counts),
        patch_strategy_count_deltas=_diff_counts(baseline.patch_strategy_counts, candidate.patch_strategy_counts),
        dynamic_delivery_class_count_deltas=_diff_counts(
            baseline.dynamic_delivery_class_counts,
            candidate.dynamic_delivery_class_counts,
        ),
        convergence_decision_count_deltas=_diff_counts(
            baseline.convergence_decision_counts,
            candidate.convergence_decision_counts,
        ),
        convergence_conflict_reason_count_deltas=_diff_counts(
            baseline.convergence_conflict_reason_counts,
            candidate.convergence_conflict_reason_counts,
        ),
        convergence_shape_family_count_deltas=_diff_counts(
            baseline.convergence_shape_family_counts,
            candidate.convergence_shape_family_counts,
        ),
        patch_convergence_blocked_count_delta=(
            candidate.patch_convergence_blocked_count - baseline.patch_convergence_blocked_count
        ),
        top_reason_code_deltas=_diff_counts(_reason_code_counts(baseline.top_reason_codes), _reason_code_counts(candidate.top_reason_codes)),
    )
