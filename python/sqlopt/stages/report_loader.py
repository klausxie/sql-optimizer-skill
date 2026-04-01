from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import read_json, read_jsonl
from ..run_paths import canonical_paths
from ..application.run_selection import selection_scope
from .report_models import ManifestEvent, ReportInputs, ReportStateSnapshot


def _read_jsonl_required(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl(path)


def _read_json_required(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    row = read_json(path)
    if isinstance(row, dict):
        return row
    return default


def _embedded_verification_rows(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for collection in collections:
        for row in collection:
            verification = row.get("verification") if isinstance(row, dict) else None
            if isinstance(verification, dict):
                rows.append(dict(verification))
    return rows


def load_report_inputs(run_dir: Path) -> ReportInputs:
    paths = canonical_paths(run_dir)
    state = _read_json_required(paths.state_path, {"phase_status": {}})
    plan = _read_json_required(paths.plan_path, {})
    units = _read_jsonl_required(paths.scan_units_path)
    proposals = _read_jsonl_required(paths.proposals_path)
    acceptance = _read_jsonl_required(paths.acceptance_path)
    patches = _read_jsonl_required(paths.patches_path)
    active_sql_keys = {
        str(row)
        for row in ((dict(plan.get("selection") or {}).get("selected_sql_keys")) or (plan.get("sql_keys") or []))
        if str(row).strip()
    }
    verification_rows = _embedded_verification_rows(units, proposals, acceptance, patches)
    if active_sql_keys:
        verification_rows = [
            row for row in verification_rows if not str(row.get("sql_key") or "").strip() or str(row.get("sql_key") or "") in active_sql_keys
        ]
    return ReportInputs(
        units=units,
        proposals=proposals,
        acceptance=acceptance,
        patches=patches,
        state=ReportStateSnapshot(
            phase_status=dict(state.get("phase_status") or {}),
            attempts_by_phase=dict(state.get("attempts_by_phase") or {}),
            selection_scope=selection_scope(plan),
        ),
        manifest_rows=[ManifestEvent.from_row(row) for row in _read_jsonl_required(paths.manifest_path)],
        verification_rows=verification_rows,
    )
