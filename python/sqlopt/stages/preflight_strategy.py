from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..platforms.base import PlatformCapabilities
from ..platforms.dispatch import get_platform_capabilities


@dataclass(frozen=True)
class DbCheckPolicy:
    enabled: bool
    reason: str | None
    capabilities: PlatformCapabilities


@dataclass(frozen=True)
class LlmCheckPolicy:
    enabled: bool
    mode: str
    reason: str | None


@dataclass(frozen=True)
class ScannerCheckPolicy:
    enabled: bool
    reason: str | None


@dataclass(frozen=True)
class PreflightPolicy:
    db: DbCheckPolicy
    llm: LlmCheckPolicy
    scanner: ScannerCheckPolicy


def _resolve_platform_capabilities(config: dict[str, Any] | None) -> PlatformCapabilities:
    if not isinstance(config, dict):
        return PlatformCapabilities()
    db_cfg = (config.get("db", {}) if isinstance(config, dict) else {}) or {}
    if str(db_cfg.get("platform") or "").strip():
        return get_platform_capabilities(config)
    return PlatformCapabilities()


def _build_db_policy(config: dict[str, Any] | None) -> DbCheckPolicy:
    validate_cfg = (config.get("validate", {}) if isinstance(config, dict) else {}) or {}
    capabilities = _resolve_platform_capabilities(config)
    if not bool(validate_cfg.get("db_reachable", False)):
        return DbCheckPolicy(enabled=False, reason="validate.db_reachable=false", capabilities=capabilities)
    if not capabilities.supports_connectivity_check:
        return DbCheckPolicy(
            enabled=False,
            reason="platform capability disables connectivity check",
            capabilities=capabilities,
        )
    return DbCheckPolicy(enabled=True, reason=None, capabilities=capabilities)


def _build_llm_policy(config: dict[str, Any] | None) -> LlmCheckPolicy:
    llm_cfg = (config.get("llm", {}) if isinstance(config, dict) else {}) or {}
    if not bool(llm_cfg.get("enabled", False)):
        return LlmCheckPolicy(enabled=False, mode="disabled", reason="llm.enabled=false")
    provider = str(llm_cfg.get("provider", "opencode_builtin"))
    if provider == "direct_openai_compatible":
        return LlmCheckPolicy(enabled=True, mode="direct_openai_compatible", reason=None)
    if provider == "opencode_run":
        return LlmCheckPolicy(enabled=True, mode="opencode_run", reason=None)
    return LlmCheckPolicy(enabled=False, mode="disabled", reason=f"provider={provider}")


def _build_scanner_policy(config: dict[str, Any] | None) -> ScannerCheckPolicy:
    java_cfg = (((config or {}).get("scan", {}) or {}).get("java_scanner", {}) or {})
    jar_path = str(java_cfg.get("jar_path") or "").strip()
    if not jar_path:
        return ScannerCheckPolicy(enabled=False, reason="scan.java_scanner.jar_path not set")
    return ScannerCheckPolicy(enabled=True, reason=None)


def build_preflight_policy(config: dict[str, Any] | None) -> PreflightPolicy:
    return PreflightPolicy(
        db=_build_db_policy(config),
        llm=_build_llm_policy(config),
        scanner=_build_scanner_policy(config),
    )
