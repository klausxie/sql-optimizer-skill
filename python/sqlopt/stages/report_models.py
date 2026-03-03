from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReportStateSnapshot:
    phase_status: dict[str, Any]
    attempts_by_phase: dict[str, Any]


@dataclass(frozen=True)
class ReportInputs:
    units: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    acceptance: list[dict[str, Any]]
    patches: list[dict[str, Any]]
    state: ReportStateSnapshot
    manifest_rows: list["ManifestEvent"]


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
class RunReportSummary:
    generated_at: str
    verdict: str
    release_readiness: str
    top_blockers: list[dict[str, Any]]
    next_actions: list[dict[str, Any]]
    prioritized_sql_keys: list[dict[str, Any]]

    def to_contract(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "verdict": self.verdict,
            "release_readiness": self.release_readiness,
            "top_blockers": self.top_blockers,
            "next_actions": self.next_actions,
            "prioritized_sql_keys": self.prioritized_sql_keys,
        }


@dataclass(frozen=True)
class RunReportItems:
    units: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    acceptance: list[dict[str, Any]]
    patches: list[dict[str, Any]]

    def to_contract(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "proposals": self.proposals,
            "acceptance": self.acceptance,
            "patches": self.patches,
        }


@dataclass(frozen=True)
class RunReportDocument:
    run_id: str
    mode: str
    llm_gate: dict[str, Any] | None
    policy: dict[str, Any]
    stats: dict[str, Any]
    items: RunReportItems
    summary: RunReportSummary
    contract_version: str

    def to_contract(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "llm_gate": self.llm_gate,
            "policy": self.policy,
            "stats": self.stats,
            "items": self.items.to_contract(),
            "summary": self.summary.to_contract(),
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class OpsTopologyDocument:
    run_id: str
    executor: str
    subagents: dict[str, Any]
    llm_mode: str
    llm_gate: dict[str, Any] | None
    runtime_policy: dict[str, Any]

    def to_contract(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "executor": self.executor,
            "subagents": self.subagents,
            "llm_mode": self.llm_mode,
            "llm_gate": self.llm_gate,
            "runtime_policy": self.runtime_policy,
        }


@dataclass(frozen=True)
class OpsHealthDocument:
    run_id: str
    mode: str
    generated_at: str
    status: str
    failure_count: int
    fatal_failure_count: int
    retryable_failure_count: int
    degradable_count: int
    report_json: str

    def to_contract(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "status": self.status,
            "failure_count": self.failure_count,
            "fatal_failure_count": self.fatal_failure_count,
            "retryable_failure_count": self.retryable_failure_count,
            "degradable_count": self.degradable_count,
            "report_json": self.report_json,
        }


@dataclass(frozen=True)
class ReportArtifacts:
    report: RunReportDocument
    topology: OpsTopologyDocument
    health: OpsHealthDocument
    failures: list[FailureRecord]
    state: ReportStateSnapshot
    next_actions: list[dict[str, Any]]
    top_blockers: list[dict[str, Any]]
    sql_rows: list[dict[str, Any]]
    proposal_rows: list[dict[str, Any]]

    def failures_to_contract(self) -> list[dict[str, Any]]:
        return [row.to_contract() for row in self.failures]
