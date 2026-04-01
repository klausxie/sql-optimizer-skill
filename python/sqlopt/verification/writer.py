from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import read_jsonl
from .models import VerificationRecord, VerificationSummary

_VERIFICATION_CACHE: dict[str, list[dict[str, Any]]] = {}


def _to_relative_path(path_str: str, run_dir: Path) -> str:
    """Convert absolute path to relative path from run_dir."""
    try:
        abs_path = Path(path_str)
        rel_path = abs_path.resolve().relative_to(run_dir.resolve())
        return str(rel_path).replace("\\", "/")
    except (ValueError, OSError):
        return path_str


def _compact_evidence_refs(payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Convert evidence_refs from absolute to relative paths."""
    if "evidence_refs" in payload and isinstance(payload["evidence_refs"], list):
        payload = dict(payload)
        payload["evidence_refs"] = [
            _to_relative_path(ref, run_dir) for ref in payload["evidence_refs"]
        ]
    return payload


def verification_ledger_path(run_dir: Path) -> Path:
    return run_dir / "artifacts" / "verification" / "ledger.jsonl"


def verification_summary_path(run_dir: Path) -> Path:
    return run_dir / "report.json"


def append_verification_record(run_dir: Path, validator: ContractValidator, record: VerificationRecord) -> dict[str, Any]:
    payload = record.to_contract()
    payload = _compact_evidence_refs(payload, run_dir)
    cache_key = str(run_dir.resolve())
    _VERIFICATION_CACHE.setdefault(cache_key, []).append(payload)
    return payload


def read_verification_ledger(run_dir: Path) -> list[dict[str, Any]]:
    cache_key = str(run_dir.resolve())
    if cache_key in _VERIFICATION_CACHE:
        return list(_VERIFICATION_CACHE[cache_key])
    ledger_path = verification_ledger_path(run_dir)
    if ledger_path.exists():
        return read_jsonl(ledger_path)
    return []


def write_verification_summary(
    run_dir: Path,
    validator: ContractValidator,
    summary: VerificationSummary | dict[str, Any],
) -> dict[str, Any]:
    payload = summary.to_contract() if isinstance(summary, VerificationSummary) else dict(summary)
    return payload
