from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _compact_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Remove None values from dict for compact output."""
    return {k: v for k, v in d.items() if v is not None}


def _compact_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter None values from list of dicts."""
    return [_compact_dict(item) for item in items if isinstance(item, dict) and any(v is not None for v in item.values())]


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    ok: bool
    severity: str
    reason_code: str | None = None
    detail: str | None = None
    evidence_ref: str | None = None

    def to_contract(self) -> dict[str, Any]:
        return _compact_dict({
            "name": self.name,
            "ok": self.ok,
            "severity": self.severity,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "evidence_ref": self.evidence_ref,
        })


@dataclass(frozen=True)
class VerificationRecord:
    run_id: str
    sql_key: str
    statement_key: str
    phase: str
    status: str
    reason_code: str
    reason_message: str
    evidence_refs: list[str]
    inputs: dict[str, Any]
    checks: list[VerificationCheck]
    verdict: dict[str, Any]
    created_at: str

    def to_contract(self) -> dict[str, Any]:
        return _compact_dict({
            "run_id": self.run_id,
            "sql_key": self.sql_key,
            "statement_key": self.statement_key,
            "phase": self.phase,
            "status": self.status,
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
            "evidence_refs": self.evidence_refs,
            "inputs": _compact_dict(self.inputs),
            "checks": _compact_list([row.to_contract() for row in self.checks]),
            "verdict": _compact_dict(self.verdict),
            "created_at": self.created_at,
        })


@dataclass(frozen=True)
class VerificationSummary:
    run_id: str
    total_sql: int
    records_by_phase: dict[str, int]
    verified_count: int
    partial_count: int
    unverified_count: int
    coverage_by_phase: dict[str, dict[str, Any]]
    top_reason_codes: list[dict[str, Any]]
    blocking_sql_keys: list[str]
    generated_at: str

    def to_contract(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_sql": self.total_sql,
            "records_by_phase": self.records_by_phase,
            "verified_count": self.verified_count,
            "partial_count": self.partial_count,
            "unverified_count": self.unverified_count,
            "coverage_by_phase": self.coverage_by_phase,
            "top_reason_codes": self.top_reason_codes,
            "blocking_sql_keys": self.blocking_sql_keys,
            "generated_at": self.generated_at,
        }
