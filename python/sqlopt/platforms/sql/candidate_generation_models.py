from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LowValueAssessment:
    candidate_id: str
    rule_id: str
    category: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecoveryAssessment:
    strategy: str | None = None
    reason: str = "NONE"
    candidates: list[dict[str, Any]] = field(default_factory=list)
    rule_id: str | None = None

    @property
    def succeeded(self) -> bool:
        return bool(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["succeeded"] = self.succeeded
        return payload


@dataclass
class CandidateGenerationDiagnostics:
    degradation_kind: str | None = None
    recovery_attempted: bool = False
    recovery_strategy: str | None = None
    recovery_succeeded: bool = False
    recovery_reason: str = "NONE"
    raw_candidate_count: int = 0
    validated_candidate_count: int = 0
    accepted_candidate_count: int = 0
    pruned_low_value_count: int = 0
    low_value_candidate_count: int = 0
    recovered_candidate_count: int = 0
    raw_rewrite_strategies: list[str] = field(default_factory=list)
    final_candidate_count: int = 0
    low_value_assessments: list[LowValueAssessment] = field(default_factory=list)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "degradationKind": self.degradation_kind,
            "recoveryAttempted": self.recovery_attempted,
            "recoveryStrategy": self.recovery_strategy,
            "recoverySucceeded": self.recovery_succeeded,
            "recoveryReason": self.recovery_reason,
            "rawCandidateCount": self.raw_candidate_count,
            "validatedCandidateCount": self.validated_candidate_count,
            "acceptedCandidateCount": self.accepted_candidate_count,
            "prunedLowValueCount": self.pruned_low_value_count,
            "lowValueCandidateCount": self.low_value_candidate_count,
            "recoveredCandidateCount": self.recovered_candidate_count,
            "rawRewriteStrategies": list(self.raw_rewrite_strategies),
            "finalCandidateCount": self.final_candidate_count,
        }

    def to_artifact_dict(self) -> dict[str, Any]:
        payload = self.to_summary_dict()
        payload["lowValueAssessments"] = [row.to_dict() for row in self.low_value_assessments]
        return payload


@dataclass
class CandidateGenerationOutcome:
    accepted_candidates: list[dict[str, Any]]
    recovery_candidates: list[dict[str, Any]]
    diagnostics: CandidateGenerationDiagnostics

