from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityDecision:
    capability: str
    allowed: bool
    priority: int
    reason: str | None = None


@dataclass(frozen=True)
class PatchabilityAssessment:
    eligible: bool
    allowed_capabilities: list[str] = field(default_factory=list)
    blocking_reason: str | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    capability_decisions: list[CapabilityDecision] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "allowedCapabilities": list(self.allowed_capabilities),
            "blockingReason": self.blocking_reason,
            "blockingReasons": list(self.blocking_reasons),
        }


@dataclass(frozen=True)
class RegisteredCapabilityRule:
    capability: str
    priority: int
    implementation: object


@dataclass(frozen=True)
class PlannedPatchStrategy:
    strategy_type: str
    mode: str
    reason_code: str
    replay_verified: bool | None
    fallback_from: str | None
    materialization: dict[str, object]
    ops: list[dict[str, object]]

    def to_summary_dict(self) -> dict[str, object]:
        return {
            "strategyType": self.strategy_type,
            "mode": self.mode,
            "reasonCode": self.reason_code,
            "fallbackFrom": self.fallback_from,
        }


@dataclass(frozen=True)
class RegisteredPatchStrategy:
    strategy_type: str
    priority: int
    required_capability: str
    implementation: object
