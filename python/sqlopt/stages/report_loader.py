from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import read_json, read_jsonl
from ..run_paths import canonical_paths
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


def load_report_inputs(run_dir: Path) -> ReportInputs:
    paths = canonical_paths(run_dir)
    state = _read_json_required(paths.state_path, {"phase_status": {}})
    return ReportInputs(
        units=_read_jsonl_required(paths.scan_units_path),
        proposals=_read_jsonl_required(paths.proposals_path),
        acceptance=_read_jsonl_required(paths.acceptance_path),
        patches=_read_jsonl_required(paths.patches_path),
        state=ReportStateSnapshot(
            phase_status=dict(state.get("phase_status") or {}),
            attempts_by_phase=dict(state.get("attempts_by_phase") or {}),
        ),
        manifest_rows=[ManifestEvent.from_row(row) for row in _read_jsonl_required(paths.manifest_path)],
        verification_rows=_read_jsonl_required(paths.verification_ledger_path),
    )
