from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalMatch:
    rule_id: str
    preferred_direction: str
    score_delta: int
    reason: str
    matched: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "ruleId": self.rule_id,
            "matched": self.matched,
            "preferredDirection": self.preferred_direction,
            "scoreDelta": self.score_delta,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CanonicalPreferenceSignal:
    preferred: bool
    preference_score: int
    primary_rule: str | None
    reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "preferred": self.preferred,
            "score": self.preference_score,
            "ruleId": self.primary_rule,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CanonicalAssessment:
    preference: CanonicalPreferenceSignal
    matched_rules: list[CanonicalMatch] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "CanonicalAssessment":
        return cls(
            preference=CanonicalPreferenceSignal(preferred=False, preference_score=0, primary_rule=None, reason=None),
            matched_rules=[],
        )

    def to_dict(self) -> dict[str, object]:
        payload = self.preference.to_dict()
        payload["matchedRules"] = [row.to_dict() for row in self.matched_rules]
        return payload


@dataclass(frozen=True)
class CanonicalContext:
    original_sql: str
    rewritten_sql: str
    normalized_original_sql: str
    normalized_rewritten_sql: str
    semantics: dict[str, object]
    row_count_status: str
    fingerprint_strength: str


@dataclass(frozen=True)
class RegisteredCanonicalRule:
    rule_id: str
    priority: int
    implementation: object
