from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DynamicCandidateIntentMatch:
    rule_id: str
    matched: bool
    intent: str | None = None
    blocking_reason: str | None = None
    rebuilt_template: str | None = None
    template_effective_change: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "ruleId": self.rule_id,
            "matched": self.matched,
            "intent": self.intent,
            "blockingReason": self.blocking_reason,
            "rebuiltTemplate": self.rebuilt_template,
            "templateEffectiveChange": self.template_effective_change,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DynamicCandidateIntentAssessment:
    intent: str
    template_preserving: bool
    blocking_reason: str | None = None
    primary_rule: str | None = None
    rebuilt_template: str | None = None
    template_effective_change: bool = False
    matches: list[DynamicCandidateIntentMatch] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "templatePreserving": self.template_preserving,
            "blockingReason": self.blocking_reason,
            "primaryRule": self.primary_rule,
            "rebuiltTemplate": self.rebuilt_template,
            "templateEffectiveChange": self.template_effective_change,
            "matches": [row.to_dict() for row in self.matches],
        }


@dataclass(frozen=True)
class RegisteredDynamicCandidateIntentRule:
    rule_id: str
    priority: int
    implementation: object
