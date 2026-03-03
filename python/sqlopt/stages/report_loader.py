from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import read_json, read_jsonl
from .report_models import ManifestEvent, ReportInputs, ReportStateSnapshot


def _read_jsonl_or_empty(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl(path)


def _read_json_or_default(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    row = read_json(path)
    return row if isinstance(row, dict) else default


def load_report_inputs(run_dir: Path) -> ReportInputs:
    state = _read_json_or_default(run_dir / "supervisor" / "state.json", {"phase_status": {}})
    return ReportInputs(
        units=_read_jsonl_or_empty(run_dir / "scan.sqlunits.jsonl"),
        proposals=_read_jsonl_or_empty(run_dir / "proposals" / "optimization.proposals.jsonl"),
        acceptance=_read_jsonl_or_empty(run_dir / "acceptance" / "acceptance.results.jsonl"),
        patches=_read_jsonl_or_empty(run_dir / "patches" / "patch.results.jsonl"),
        state=ReportStateSnapshot(
            phase_status=dict(state.get("phase_status") or {}),
            attempts_by_phase=dict(state.get("attempts_by_phase") or {}),
        ),
        manifest_rows=[ManifestEvent.from_row(row) for row in _read_jsonl_or_empty(run_dir / "manifest.jsonl")],
    )
