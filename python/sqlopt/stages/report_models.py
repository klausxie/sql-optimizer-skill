from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportStateSnapshot:
    phase_status: dict[str, Any]
    attempts_by_phase: dict[str, Any]
    selection_scope: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReportInputs:
    units: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    acceptance: list[dict[str, Any]]
    patches: list[dict[str, Any]]
    state: ReportStateSnapshot
    manifest_rows: list["ManifestEvent"]
    verification_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ManifestEvent:
    stage: str | None
    event: str | None
    payload: dict[str, Any]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ManifestEvent":
        return cls(
            stage=row.get("stage"),
            event=row.get("event"),
            payload=dict(row.get("payload") or {}),
        )


@dataclass(frozen=True)
class FailureRecord:
    sql_key: str | None
    reason_code: str
    status: str
    classification: str
    phase: str | None

    def to_contract(self) -> dict[str, Any]:
        return {
            "sql_key": self.sql_key,
            "reason_code": self.reason_code,
            "status": self.status,
            "classification": self.classification,
            "phase": self.phase,
        }


@dataclass(frozen=True)
class RunReportDocument:
    run_id: str
    generated_at: str
    target_stage: str
    status: str
    verdict: str
    next_action: str
    phase_status: dict[str, Any]
    stats: dict[str, Any]
    top_blockers: list[dict[str, Any]]
    selection_scope: dict[str, Any] | None = None
    validation_warnings: list[str] | None = None
    evidence_confidence: str | None = None

    def to_contract(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "target_stage": self.target_stage,
            "status": self.status,
            "verdict": self.verdict,
            "next_action": self.next_action,
            "phase_status": self.phase_status,
            "stats": {
                "sql_total": int(self.stats.get("sql_units") or 0),
                "proposal_total": int(self.stats.get("proposals") or 0),
                "accepted_total": int(self.stats.get("acceptance_pass") or 0),
                "patchable_total": int(self.stats.get("patch_applicable_count") or 0),
                "patched_total": int(self.stats.get("patch_files") or 0),
                "blocked_total": int(self.stats.get("blocked_sql_count") or 0),
            },
            "blockers": {
                "top_reason_codes": [
                    {
                        "code": str(row.get("code") or ""),
                        "count": int(row.get("count") or 0),
                    }
                    for row in self.top_blockers
                    if str(row.get("code") or "").strip()
                ]
            },
        }


@dataclass(frozen=True)
class ReportArtifacts:
    report: RunReportDocument
    failures: list[FailureRecord]
    state: ReportStateSnapshot
    next_actions: list[dict[str, Any]]
    top_blockers: list[dict[str, Any]]
    sql_rows: list[dict[str, Any]]
    proposal_rows: list[dict[str, Any]]
    diagnostics_sql_outcomes: list[dict[str, Any]] = field(default_factory=list)
    diagnostics_sql_artifacts: list[dict[str, Any]] = field(default_factory=list)
    verification_summary: dict[str, Any] = field(default_factory=dict)
    validation_warnings: list[str] | None = None
    evidence_confidence: str | None = None

    def failures_to_contract(self) -> list[dict[str, Any]]:
        return [row.to_contract() for row in self.failures]
