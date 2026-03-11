from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CandidatePatchabilityContext:
    original_sql: str
    candidate_source: str
    rewritten_sql: str
    rewrite_strategy: str


@dataclass(frozen=True)
class CandidatePatchabilityRuleMatch:
    rule_id: str
    score_delta: int
    reason: str


@dataclass(frozen=True)
class CandidatePatchabilityAssessment:
    score: int
    tier: str
    reasons: list[str] = field(default_factory=list)
    matched_rules: list[CandidatePatchabilityRuleMatch] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredCandidatePatchabilityRule:
    rule_id: str
    priority: int
    implementation: object
