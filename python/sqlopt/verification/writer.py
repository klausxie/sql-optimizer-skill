from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl, write_json
from .models import VerificationRecord, VerificationSummary


def verification_ledger_path(run_dir: Path) -> Path:
    return run_dir / "verification" / "ledger.jsonl"


def verification_summary_path(run_dir: Path) -> Path:
    return run_dir / "verification" / "summary.json"


def append_verification_record(run_dir: Path, validator: ContractValidator, record: VerificationRecord) -> dict[str, Any]:
    payload = record.to_contract()
    validator.validate("verification_record", payload)
    append_jsonl(verification_ledger_path(run_dir), payload)
    return payload


def read_verification_ledger(run_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(verification_ledger_path(run_dir))


def write_verification_summary(
    run_dir: Path,
    validator: ContractValidator,
    summary: VerificationSummary | dict[str, Any],
) -> dict[str, Any]:
    payload = summary.to_contract() if isinstance(summary, VerificationSummary) else dict(summary)
    validator.validate("verification_summary", payload)
    write_json(verification_summary_path(run_dir), payload)
    return payload
