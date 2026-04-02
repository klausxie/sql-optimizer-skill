from __future__ import annotations

from ....stages.report_stats import blocker_family_for_patch_row
from ..runtime.models import HarnessArtifacts
from .models import BenchmarkSnapshot


def _counts_from_rows(rows: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _top_reason_codes(report: dict) -> list[dict[str, int | str]]:
    blockers = report.get("blockers") or {}
    rows = blockers.get("top_reason_codes") or []
    return [
        {"code": str(row.get("code") or ""), "count": int(row.get("count") or 0)}
        for row in rows
        if str(row.get("code") or "").strip()
    ]


def _blocker_family_counts(artifacts: HarnessArtifacts) -> dict[str, int]:
    counts: dict[str, int] = {}
    if artifacts.patch_rows:
        for row in artifacts.patch_rows:
            family = blocker_family_for_patch_row(row)
            counts[family] = counts.get(family, 0) + 1
        return counts
    for row in artifacts.sql_catalog_rows:
        family = str(row.get("blocker_family") or "").strip().upper()
        if not family:
            continue
        counts[family] = counts.get(family, 0) + 1
    return counts


def snapshot_from_artifacts(artifacts: HarnessArtifacts) -> BenchmarkSnapshot:
    report = artifacts.report
    stats = report.get("stats") or {}
    state = artifacts.state
    return BenchmarkSnapshot(
        run_id=str(report.get("run_id") or state.get("run_id") or ""),
        status=str(state.get("status") or report.get("status") or ""),
        verdict=str(report.get("verdict") or ""),
        next_action=str(report.get("next_action") or ""),
        phase_status={str(k): str(v) for k, v in (report.get("phase_status") or {}).items()},
        sql_total=int(stats.get("sql_total") or 0),
        proposal_total=int(stats.get("proposal_total") or 0),
        accepted_total=int(stats.get("accepted_total") or 0),
        patchable_total=int(stats.get("patchable_total") or 0),
        patched_total=int(stats.get("patched_total") or 0),
        blocked_total=int(stats.get("blocked_total") or 0),
        blocker_family_counts=_blocker_family_counts(artifacts),
        patch_strategy_counts=_counts_from_rows(artifacts.patch_rows, "strategyType"),
        dynamic_delivery_class_counts=_counts_from_rows(artifacts.sql_catalog_rows, "dynamic_delivery_class"),
        top_reason_codes=_top_reason_codes(report),
    )
