from __future__ import annotations

from ....stages.report_stats import blocker_family_for_patch_row
from ..assertions.helpers import patch_apply_ready
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


def _convergence_counts(artifacts: HarnessArtifacts, field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in artifacts.statement_convergence_rows:
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _patch_convergence_blocked_count(artifacts: HarnessArtifacts) -> int:
    total = 0
    for row in artifacts.patch_rows:
        code = str(((row.get("selectionReason") or {}).get("code") or "")).strip()
        if code.startswith("PATCH_CONVERGENCE_"):
            total += 1
    return total


def _top_reason_codes(artifacts: HarnessArtifacts) -> list[dict[str, int | str]]:
    counts: dict[str, int] = {}
    for row in artifacts.acceptance_rows:
        code = str(((row.get("feedback") or {}).get("reason_code") or "")).strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    for row in artifacts.patch_rows:
        code = str(((row.get("selectionReason") or {}).get("code") or "")).strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    for row in artifacts.manifest_rows:
        code = str(((row.get("payload") or {}).get("reason_code") or "")).strip()
        if code:
            counts[code] = counts.get(code, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"code": code, "count": count} for code, count in ordered[:10]]


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


def _sql_total(artifacts: HarnessArtifacts) -> int:
    if artifacts.scan_rows:
        return len(artifacts.scan_rows)
    return len(artifacts.sql_catalog_rows)


def _accepted_total(artifacts: HarnessArtifacts) -> int:
    return sum(1 for row in artifacts.acceptance_rows if str(row.get("status") or "").strip().upper() == "PASS")


def _patchable_total(artifacts: HarnessArtifacts) -> int:
    return sum(1 for row in artifacts.patch_rows if patch_apply_ready(row))


def _patched_total(artifacts: HarnessArtifacts) -> int:
    return sum(1 for row in artifacts.patch_rows if list(row.get("patchFiles") or []))


def _blocked_total(artifacts: HarnessArtifacts, blocker_family_counts: dict[str, int]) -> int:
    if blocker_family_counts:
        return sum(count for family, count in blocker_family_counts.items() if family != "READY")
    return max(_sql_total(artifacts) - _patchable_total(artifacts), 0)


def snapshot_from_artifacts(artifacts: HarnessArtifacts) -> BenchmarkSnapshot:
    report = artifacts.report
    state = artifacts.state
    blocker_family_counts = _blocker_family_counts(artifacts)
    return BenchmarkSnapshot(
        run_id=str(report.get("run_id") or state.get("run_id") or ""),
        status=str(state.get("status") or report.get("status") or ""),
        verdict=str(report.get("verdict") or ""),
        next_action=str(report.get("next_action") or ""),
        phase_status={str(k): str(v) for k, v in (report.get("phase_status") or {}).items()},
        sql_total=_sql_total(artifacts),
        proposal_total=len(artifacts.proposal_rows),
        accepted_total=_accepted_total(artifacts),
        patchable_total=_patchable_total(artifacts),
        patched_total=_patched_total(artifacts),
        blocked_total=_blocked_total(artifacts, blocker_family_counts),
        blocker_family_counts=blocker_family_counts,
        patch_strategy_counts=_counts_from_rows(artifacts.patch_rows, "strategyType"),
        dynamic_delivery_class_counts=_counts_from_rows(artifacts.sql_catalog_rows, "dynamic_delivery_class"),
        convergence_decision_counts=_convergence_counts(artifacts, "convergenceDecision"),
        convergence_conflict_reason_counts=_convergence_counts(artifacts, "conflictReason"),
        convergence_shape_family_counts=_convergence_counts(artifacts, "shapeFamily"),
        patch_convergence_blocked_count=_patch_convergence_blocked_count(artifacts),
        top_reason_codes=_top_reason_codes(artifacts),
    )
