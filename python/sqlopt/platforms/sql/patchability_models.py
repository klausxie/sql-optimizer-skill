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
    aggregation_constraint_family: str | None = None
    aggregation_capability_tier: str | None = None
    aggregation_safe_baseline_family: str | None = None
    dynamic_shape_family: str | None = None
    dynamic_capability_tier: str | None = None
    dynamic_patch_surface: str | None = None
    dynamic_blocking_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "allowedCapabilities": list(self.allowed_capabilities),
            "blockingReason": self.blocking_reason,
            "blockingReasons": list(self.blocking_reasons),
            "aggregationConstraintFamily": self.aggregation_constraint_family,
            "aggregationCapabilityTier": self.aggregation_capability_tier,
            "aggregationSafeBaselineFamily": self.aggregation_safe_baseline_family,
            "dynamicShapeFamily": self.dynamic_shape_family,
            "dynamicCapabilityTier": self.dynamic_capability_tier,
            "dynamicPatchSurface": self.dynamic_patch_surface,
            "dynamicBlockingReason": self.dynamic_blocking_reason,
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
