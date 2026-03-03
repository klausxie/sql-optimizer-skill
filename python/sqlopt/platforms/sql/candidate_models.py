from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Candidate:
    id: str
    source: str
    rewritten_sql: str
    rewrite_strategy: str


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str | None
    source: str | None
    semantic_match: bool
    improved: bool
    after_cost: float | None

    def to_contract(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "source": self.source,
            "semanticMatch": self.semantic_match,
            "improved": self.improved,
            "afterCost": self.after_cost,
        }


@dataclass(frozen=True)
class EquivalenceCheck:
    checked: bool | None
    method: str
    row_count: dict[str, Any] | None = None
    evidence_refs: list[Any] | None = None

    def to_contract(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "method": self.method,
            "rowCount": self.row_count,
            "evidenceRefs": list(self.evidence_refs or []),
        }


@dataclass(frozen=True)
class PerfComparison:
    checked: bool
    method: str
    before_summary: dict[str, Any]
    after_summary: dict[str, Any]
    reason_codes: list[str]
    improved: bool | None
    evidence_refs: list[Any]

    def to_contract(self, *, reason_codes: list[str] | None = None) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "method": self.method,
            "beforeSummary": self.before_summary,
            "afterSummary": self.after_summary,
            "reasonCodes": list(self.reason_codes if reason_codes is None else reason_codes),
            "improved": self.improved,
            "evidenceRefs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class CandidateSelectionResult:
    rewritten_sql: str
    selected_candidate_id: str | None
    selected_candidate_source: str | None
    candidate_evaluations: list[CandidateEvaluation]
    equivalence: EquivalenceCheck
    perf: PerfComparison

    def candidate_evaluations_to_contract(self) -> list[dict[str, Any]]:
        return [row.to_contract() for row in self.candidate_evaluations]
