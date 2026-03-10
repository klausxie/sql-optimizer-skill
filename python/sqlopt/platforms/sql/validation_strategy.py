from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..base import PlatformCapabilities
from ..dispatch import get_platform_capabilities

CompareRunner = Callable[[dict[str, Any], str, str, Path], dict[str, Any]]


@dataclass(frozen=True)
class ValidationComparePolicy:
    capabilities: PlatformCapabilities
    semantics_enabled: bool
    plan_enabled: bool
    semantics_skip_reason: str | None
    plan_skip_reason: str | None


def _semantics_skipped_result(reason_code: str) -> dict[str, Any]:
    return {
        "checked": False,
        "method": "capability_gate",
        "rowCount": {"status": "SKIPPED"},
        "keySetHash": {"status": "SKIPPED", "reason": "semantics_capability_disabled"},
        "rowSampleHash": {"status": "SKIPPED", "reason": "semantics_capability_disabled"},
        "evidenceRefs": [],
        "reasonCodes": [reason_code],
    }


def _plan_skipped_result(reason_code: str) -> dict[str, Any]:
    return {
        "checked": False,
        "method": "capability_gate",
        "beforeSummary": {},
        "afterSummary": {},
        "reasonCodes": [reason_code],
        "improved": None,
        "evidenceRefs": [],
    }


def resolve_platform_capabilities(config: dict[str, Any] | None) -> PlatformCapabilities:
    if not isinstance(config, dict):
        return PlatformCapabilities()
    db_cfg = (config.get("db", {}) if isinstance(config, dict) else {}) or {}
    if str(db_cfg.get("platform") or "").strip():
        return get_platform_capabilities(config)
    return PlatformCapabilities()


def build_compare_policy(config: dict[str, Any] | None) -> ValidationComparePolicy:
    capabilities = resolve_platform_capabilities(config)
    validate_cfg = (config.get("validate", {}) if isinstance(config, dict) else {}) or {}

    semantics_enabled = bool(capabilities.supports_semantic_compare)
    semantics_skip_reason = None if semantics_enabled else "VALIDATE_SEMANTIC_COMPARE_DISABLED"

    plan_config_enabled = bool(validate_cfg.get("plan_compare_enabled", True))
    plan_enabled = bool(capabilities.supports_plan_compare) and plan_config_enabled
    if plan_enabled:
        plan_skip_reason = None
    elif not capabilities.supports_plan_compare:
        plan_skip_reason = "VALIDATE_PLAN_COMPARE_DISABLED"
    else:
        plan_skip_reason = "VALIDATE_PLAN_COMPARE_CONFIG_DISABLED"

    return ValidationComparePolicy(
        capabilities=capabilities,
        semantics_enabled=semantics_enabled,
        plan_enabled=plan_enabled,
        semantics_skip_reason=semantics_skip_reason,
        plan_skip_reason=plan_skip_reason,
    )


def run_semantics_compare(
    policy: ValidationComparePolicy,
    runner: CompareRunner,
    config: dict[str, Any],
    original_sql: str,
    rewritten_sql: str,
    evidence_dir: Path,
) -> dict[str, Any]:
    if policy.semantics_enabled:
        return runner(config, original_sql, rewritten_sql, evidence_dir)
    return _semantics_skipped_result(str(policy.semantics_skip_reason))


def run_plan_compare(
    policy: ValidationComparePolicy,
    runner: CompareRunner,
    config: dict[str, Any],
    original_sql: str,
    rewritten_sql: str,
    evidence_dir: Path,
) -> dict[str, Any]:
    if policy.plan_enabled:
        return runner(config, original_sql, rewritten_sql, evidence_dir)
    return _plan_skipped_result(str(policy.plan_skip_reason))
