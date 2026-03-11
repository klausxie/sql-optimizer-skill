from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CandidateSelectionRank:
    effective_change: bool
    patchability_score: int
    canonical_score: int
    improved: bool
    after_cost: float

    def as_tuple(self) -> tuple[int, int, int, int, float]:
        return (
            1 if self.effective_change else 0,
            self.patchability_score,
            self.canonical_score,
            1 if self.improved else 0,
            -self.after_cost,
        )

    def to_trace_list(self) -> list[int | float | None]:
        cost_rank: float | None
        if math.isfinite(self.after_cost):
            cost_rank = -self.after_cost
        else:
            cost_rank = None
        return [
            1 if self.effective_change else 0,
            self.patchability_score,
            self.canonical_score,
            1 if self.improved else 0,
            cost_rank,
        ]


@dataclass(frozen=True)
class CandidateCanonicalizationAssessmentEntry:
    candidate_id: str
    source: str
    rewritten_sql: str
    preferred: bool
    rule_id: str | None
    score: int
    reason: str | None
    matched_rules: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "candidateId": self.candidate_id,
            "source": self.source,
            "rewrittenSql": self.rewritten_sql,
            "preferred": self.preferred,
            "ruleId": self.rule_id,
            "score": self.score,
            "reason": self.reason,
            "matchedRules": list(self.matched_rules),
        }


@dataclass(frozen=True)
class CandidateSelectionTraceEntry:
    candidate_id: str
    semantic_match: bool
    effective_change: bool
    patchability_score: int
    canonical_score: int
    improved: bool
    after_cost: float | None
    rank: CandidateSelectionRank

    def to_dict(self) -> dict[str, object]:
        return {
            "candidateId": self.candidate_id,
            "semanticMatch": self.semantic_match,
            "effectiveChange": self.effective_change,
            "patchabilityScore": self.patchability_score,
            "canonicalScore": self.canonical_score,
            "improved": self.improved,
            "afterCost": self.after_cost,
            "rank": self.rank.to_trace_list(),
        }
